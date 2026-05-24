<template>
  <div class="px-4 py-3 bg-white">
    <div
      ref="wrapperRef"
      class="relative bg-surface border border-outline-variant rounded-2xl focus-within:border-brand focus-within:shadow-glow transition-all duration-200"
    >
      <!-- Inner content (overflow-hidden for rounded corners) -->
      <div class="overflow-hidden rounded-2xl">
        <!-- Reply preview bar -->
        <div
          v-if="replyTo"
          class="flex items-center gap-2 px-3 py-2 bg-brand-light/20 border-b border-outline-variant"
        >
          <div class="flex-1 min-w-0 border-l-2 border-brand pl-2">
            <span class="text-[11px] text-brand font-semibold">Replying to {{ replyTo.senderName }}</span>
            <p class="text-[11px] text-on-surface-variant truncate">{{ replyTo.content }}</p>
          </div>
          <button
            class="w-6 h-6 rounded-lg flex items-center justify-center text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors cursor-pointer"
            @click="emit('cancel-reply')"
          >
            <el-icon :size="12"><Close /></el-icon>
          </button>
        </div>

        <!-- contenteditable div -->
        <div
          ref="editorRef"
          contenteditable="true"
          class="w-full min-h-[80px] max-h-[200px] px-4 pt-3 pb-1 bg-transparent text-[13px] text-on-surface outline-none resize-none leading-relaxed overflow-y-auto custom-scrollbar"
          :data-placeholder="placeholder"
          @input="onEditorInput"
          @keydown="onEditorKeydown"
          @compositionstart="isComposing = true"
          @compositionend="isComposing = false"
          @paste="onPaste"
        ></div>

        <!-- Bottom action bar -->
        <div class="flex items-center justify-between px-2 py-1.5">
          <!-- Left actions -->
          <div class="flex items-center gap-0.5">
            <button class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant/60 hover:text-on-surface-variant hover:bg-surface-container transition-colors cursor-pointer">
              <el-icon :size="18"><Plus /></el-icon>
            </button>
            <button class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant/60 hover:text-on-surface-variant hover:bg-surface-container transition-colors cursor-pointer">
              <el-icon :size="18"><Paperclip /></el-icon>
            </button>
          </div>

          <!-- Send button -->
          <button
            class="w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200 cursor-pointer"
            :class="hasContent ? 'bg-slate-700 text-white hover:bg-slate-600' : 'text-on-surface-variant/40'"
            :disabled="!hasContent"
            @click="handleSend"
          >
            <el-icon :size="18"><Promotion /></el-icon>
          </button>
        </div>
      </div>

      <!-- MentionPicker dropdown (outside overflow-hidden so it's not clipped) -->
      <MentionPicker
        v-if="mentionState.visible"
        ref="mentionPickerRef"
        :agents="agents"
        :query="mentionState.query"
        :position="mentionState.position"
        @select="onMentionSelect"
        @dismiss="dismissMentionPicker"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { Plus, Paperclip, Promotion, Close } from '@element-plus/icons-vue'
import MentionPicker from './MentionPicker.vue'
import type { ChatAgent, ReplyPreview } from '@/types/chat'

const props = withDefaults(defineProps<{
  modelValue: string
  agents: ChatAgent[]
  replyTo: ReplyPreview | null
  placeholder?: string
}>(), {
  placeholder: 'Ask Nexus anything...',
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: [content: string, mentions: string[], replyToId?: string]
  'cancel-reply': []
}>()

const wrapperRef = ref<HTMLDivElement | null>(null)
const editorRef = ref<HTMLDivElement | null>(null)
const mentionPickerRef = ref<{ navigate: (dir: 1 | -1) => void; confirmSelection: () => void } | null>(null)

const isComposing = ref(false)
const mentionState = ref<{
  visible: boolean
  query: string
  startIndex: number
  position: { top: number; left: number }
}>({
  visible: false,
  query: '',
  startIndex: 0,
  position: { top: 0, left: 0 },
})

const hasContent = computed(() => {
  if (!editorRef.value) return false
  const text = editorRef.value.textContent?.trim() ?? ''
  return text.length > 0
})

function getTextContent(): { text: string; mentions: string[] } {
  if (!editorRef.value) return { text: '', mentions: [] }
  let text = ''
  const mentions: string[] = []

  const walk = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      text += node.textContent ?? ''
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      const el = node as HTMLElement
      if (el.dataset.mentionId) {
        mentions.push(el.dataset.mentionId)
        text += `@${el.dataset.mentionName || el.dataset.mentionId}`
      } else {
        el.childNodes.forEach(walk)
      }
    }
  }

  editorRef.value.childNodes.forEach(walk)
  return { text: text.replace(/​/g, '').trim(), mentions }
}

function syncContent() {
  const { text } = getTextContent()
  emit('update:modelValue', text)
}

function autoResize() {
  if (!editorRef.value) return
  editorRef.value.style.height = 'auto'
  const scrollHeight = editorRef.value.scrollHeight
  editorRef.value.style.height = Math.min(scrollHeight, 200) + 'px'
}

function detectMentionTrigger() {
  if (!editorRef.value) return

  const selection = window.getSelection()
  if (!selection || selection.rangeCount === 0) {
    mentionState.value.visible = false
    return
  }

  const range = selection.getRangeAt(0)
  const textNode = range.startContainer
  if (textNode.nodeType !== Node.TEXT_NODE || !editorRef.value.contains(textNode)) {
    mentionState.value.visible = false
    return
  }

  const text = textNode.textContent ?? ''
  const cursorOffset = range.startOffset

  // Walk backward from cursor to find @
  let atIndex = -1
  for (let i = cursorOffset - 1; i >= 0; i--) {
    const char = text[i]
    if (char === '@') {
      // Check if preceded by whitespace or at start
      if (i === 0 || /\s/.test(text[i - 1])) {
        atIndex = i
        break
      }
    } else if (/\s/.test(char)) {
      break
    }
  }

  if (atIndex >= 0) {
    const query = text.slice(atIndex + 1, cursorOffset)
    mentionState.value.visible = true
    mentionState.value.query = query
    mentionState.value.startIndex = atIndex

    // Compute position
    const cloneRange = range.cloneRange()
    cloneRange.setStart(textNode, atIndex)
    cloneRange.setEnd(textNode, atIndex)
    const rect = cloneRange.getBoundingClientRect()
    const wrapperRect = wrapperRef.value!.getBoundingClientRect()
    mentionState.value.position = {
      top: rect.top - wrapperRect.top,
      left: Math.max(0, rect.left - wrapperRect.left - 8),
    }
  } else {
    mentionState.value.visible = false
  }
}

function onEditorInput() {
  syncContent()
  autoResize()
  detectMentionTrigger()
}

function onEditorKeydown(e: KeyboardEvent) {
  if (isComposing.value) return

  // Mention picker navigation
  if (mentionState.value.visible) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      mentionPickerRef.value?.navigate(e.key === 'ArrowDown' ? 1 : -1)
      return
    }
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault()
      mentionPickerRef.value?.confirmSelection()
      return
    }
    if (e.key === 'Escape') {
      e.preventDefault()
      dismissMentionPicker()
      return
    }
  }

  // Enter to send (without Shift)
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
    return
  }

  // Backspace: delete whole chip if cursor after it
  if (e.key === 'Backspace') {
    handleBackspace(e)
  }
}

function handleBackspace(e: KeyboardEvent) {
  if (!editorRef.value) return

  const selection = window.getSelection()
  if (!selection || selection.rangeCount === 0) return

  const range = selection.getRangeAt(0)
  const textNode = range.startContainer

  if (textNode.nodeType === Node.TEXT_NODE && range.startOffset === 0) {
    const prev = textNode.previousSibling
    if (prev && prev.nodeType === Node.ELEMENT_NODE && (prev as HTMLElement).dataset.mentionId) {
      e.preventDefault()
      prev.remove()
      syncContent()
    }
  }
}

function onMentionSelect(agent: ChatAgent) {
  if (!editorRef.value) return

  const selection = window.getSelection()
  if (!selection || selection.rangeCount === 0) return

  const range = selection.getRangeAt(0)
  const textNode = range.startContainer

  if (textNode.nodeType !== Node.TEXT_NODE) return

  // Delete @query text
  const deleteRange = range.cloneRange()
  deleteRange.setStart(textNode, mentionState.value.startIndex)
  deleteRange.setEnd(textNode, range.startOffset)
  deleteRange.deleteContents()

  // Create mention chip
  const chip = document.createElement('span')
  chip.setAttribute('contenteditable', 'false')
  chip.setAttribute('data-mention-id', agent.id)
  chip.setAttribute('data-mention-name', agent.name)
  chip.className = 'inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded-md bg-brand-light text-brand text-[12px] font-medium select-none cursor-pointer'
  chip.textContent = `@${agent.name}`

  // Insert chip
  range.insertNode(chip)

  // Insert zero-width space for cursor positioning
  const zwsp = document.createTextNode('​')
  chip.after(zwsp)

  // Move cursor after chip
  const newRange = document.createRange()
  newRange.setStart(zwsp, 1)
  newRange.collapse(true)
  selection.removeAllRanges()
  selection.addRange(newRange)

  dismissMentionPicker()
  syncContent()
}

function dismissMentionPicker() {
  mentionState.value.visible = false
}

function onPaste(e: ClipboardEvent) {
  e.preventDefault()
  const text = e.clipboardData?.getData('text/plain') ?? ''
  document.execCommand('insertText', false, text)
}

function handleSend() {
  const { text, mentions } = getTextContent()
  if (!text) return

  const replyToId = props.replyTo?.messageId
  emit('send', text, mentions, replyToId)
  emit('update:modelValue', '')

  // Clear editor
  if (editorRef.value) {
    editorRef.value.innerHTML = ''
    autoResize()
  }
}

function focus() {
  editorRef.value?.focus()
}

// Sync modelValue changes from outside
watch(() => props.modelValue, (newVal) => {
  if (!editorRef.value) return
  const { text } = getTextContent()
  if (newVal !== text) {
    editorRef.value.innerHTML = newVal
    autoResize()
  }
})

// Click outside to dismiss picker
function onDocClick(e: MouseEvent) {
  if (!wrapperRef.value?.contains(e.target as Node)) {
    dismissMentionPicker()
  }
}

onMounted(() => {
  document.addEventListener('mousedown', onDocClick)
  // Initialize content from modelValue
  if (editorRef.value && props.modelValue) {
    editorRef.value.innerHTML = props.modelValue
    autoResize()
  }
})

onUnmounted(() => {
  document.removeEventListener('mousedown', onDocClick)
})

defineExpose({ focus })
</script>

<style scoped>
[contenteditable][data-placeholder]:empty::before {
  content: attr(data-placeholder);
  color: var(--color-on-surface-variant);
  opacity: 0.6;
  pointer-events: none;
}
</style>