<template>
  <div class="px-4 py-3 bg-white">
    <!-- Hidden file input -->
    <input
      ref="fileInputRef"
      type="file"
      multiple
      class="hidden"
      @change="onFilesSelected"
    />

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

        <!-- Attached files bar -->
        <div
          v-if="attachedFiles.length > 0"
          class="flex flex-wrap gap-1.5 px-3 pt-2 pb-1 border-b border-outline-variant"
        >
          <div
            v-for="(file, idx) in attachedFiles"
            :key="idx"
            class="flex items-center gap-1.5 px-2 py-1 rounded-lg border text-[11px] text-on-surface max-w-[200px] group transition-colors"
            :class="file.uploading
              ? 'bg-brand-light/30 border-brand/30 text-brand'
              : 'bg-surface-container-low border-outline-variant'"
          >
            <el-icon :size="12" class="shrink-0" :class="file.uploading ? 'animate-spin text-brand' : 'text-on-surface-variant'">
              <Loading v-if="file.uploading" />
              <Document v-else />
            </el-icon>
            <span class="truncate">{{ file.name }}</span>
            <button
              v-if="!file.uploading"
              class="w-4 h-4 rounded flex items-center justify-center text-on-surface-variant/50 hover:text-error hover:bg-error-light opacity-0 group-hover:opacity-100 transition-all cursor-pointer shrink-0"
              @click="removeFile(idx)"
            >
              <el-icon :size="10"><Close /></el-icon>
            </button>
          </div>
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
            <button
              class="w-8 h-8 rounded-lg flex items-center justify-center transition-colors cursor-pointer"
              :class="attachedFiles.length > 0 ? 'text-brand bg-brand-light/40 hover:bg-brand-light' : 'text-on-surface-variant/60 hover:text-on-surface-variant hover:bg-surface-container'"
              :title="attachedFiles.length > 0 ? `${attachedFiles.length} file(s) attached` : 'Attach files'"
              @click="fileInputRef?.click()"
            >
              <el-icon :size="18"><Paperclip /></el-icon>
            </button>
          </div>

          <!-- Send / Stop button -->
          <button
            v-if="streaming"
            class="w-8 h-8 rounded-lg flex items-center justify-center bg-red-500 text-white hover:bg-red-600 transition-all duration-200 cursor-pointer"
            @click="emit('stop')"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
              <rect x="6" y="6" width="12" height="12" rx="1" />
            </svg>
          </button>
          <button
            v-else
            class="w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200 cursor-pointer"
            :class="hasContent || attachedFiles.length > 0 ? 'bg-slate-700 text-white hover:bg-slate-600' : 'text-on-surface-variant/40'"
            :disabled="!hasContent && attachedFiles.length === 0"
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
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { Plus, Paperclip, Promotion, Close, Document, Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import MentionPicker from './MentionPicker.vue'
import { filesApi } from '@/api/files'
import type { ChatAgent, ReplyPreview } from '@/types/chat'

const props = withDefaults(defineProps<{
  modelValue: string
  htmlDraft: string
  agents: ChatAgent[]
  replyTo: ReplyPreview | null
  placeholder?: string
  streaming?: boolean
}>(), {
  placeholder: 'Ask anything...',
  streaming: false,
  htmlDraft: '',
})

const emit = defineEmits<{
  'update:modelValue': [value: string, html?: string]
  send: [content: string, mentions: string[], replyToId?: string]
  stop: []
  'cancel-reply': []
}>()

const wrapperRef = ref<HTMLDivElement | null>(null)
const editorRef = ref<HTMLDivElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const mentionPickerRef = ref<{ navigate: (dir: 1 | -1) => void; confirmSelection: () => void } | null>(null)

const isComposing = ref(false)
const hasContent = ref(false)

// ── Attached files ──
interface AttachedFile {
  name: string
  path: string       // server-side path after upload
  uploading: boolean
}
const attachedFiles = ref<AttachedFile[]>([])

async function onFilesSelected(e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files || input.files.length === 0) return

  const selected = Array.from(input.files)
  input.value = ''

  // Add placeholder entries with uploading=true
  const placeholders: AttachedFile[] = selected.map(f => ({
    name: f.name,
    path: '',
    uploading: true,
  }))
  const startIdx = attachedFiles.value.length
  attachedFiles.value.push(...placeholders)

  try {
    const { paths } = await filesApi.upload(selected)
    paths.forEach((p, i) => {
      attachedFiles.value[startIdx + i].path = p
      attachedFiles.value[startIdx + i].uploading = false
    })
  } catch {
    // Remove the failed placeholders
    attachedFiles.value.splice(startIdx, selected.length)
    ElMessage({ message: '文件上传失败，请重试', type: 'error', duration: 2000, plain: true })
  }
}

function removeFile(idx: number) {
  attachedFiles.value.splice(idx, 1)
}

// ── Mention state ──
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

function syncHasContent() {
  if (!editorRef.value) { hasContent.value = false; return }
  hasContent.value = (editorRef.value.textContent?.trim() ?? '').length > 0
}

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
  const html = editorRef.value?.innerHTML ?? ''
  emit('update:modelValue', text, html)
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

  let atIndex = -1
  for (let i = cursorOffset - 1; i >= 0; i--) {
    const char = text[i]
    if (char === '@') {
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
  syncHasContent()
  autoResize()
  detectMentionTrigger()
}

function onEditorKeydown(e: KeyboardEvent) {
  if (isComposing.value) return

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

  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (!props.streaming) handleSend()
    return
  }

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

  const deleteRange = range.cloneRange()
  deleteRange.setStart(textNode, mentionState.value.startIndex)
  deleteRange.setEnd(textNode, range.startOffset)
  deleteRange.deleteContents()

  const chip = document.createElement('span')
  chip.setAttribute('contenteditable', 'false')
  chip.setAttribute('data-mention-id', agent.id)
  chip.setAttribute('data-mention-name', agent.name)
  chip.className = 'inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded-md bg-brand-light text-brand text-[12px] font-medium select-none cursor-pointer'
  chip.textContent = `@${agent.name}`

  range.insertNode(chip)
  const zwsp = document.createTextNode('​')
  chip.after(zwsp)

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
  if (props.streaming) return
  const { text, mentions } = getTextContent()
  if (!text && attachedFiles.value.length === 0) return

  // Don't send while any file is still uploading
  if (attachedFiles.value.some(f => f.uploading)) {
    ElMessage({ message: '文件上传中，请稍候', type: 'warning', duration: 1500, plain: true })
    return
  }

  // Append server-side file paths to content
  let finalContent = text
  if (attachedFiles.value.length > 0) {
    const pathLines = attachedFiles.value.map(f => `[file: ${f.path}]`).join('\n')
    finalContent = text ? `${text}\n${pathLines}` : pathLines
  }

  const replyToId = props.replyTo?.messageId
  emit('send', finalContent, mentions, replyToId)
  emit('update:modelValue', '')

  // Clear editor and files
  if (editorRef.value) {
    editorRef.value.innerHTML = ''
    hasContent.value = false
    autoResize()
  }
  attachedFiles.value = []
}

function focus() {
  editorRef.value?.focus()
}

watch(() => props.htmlDraft, (newHtml) => {
  if (!editorRef.value) return
  const currentHtml = editorRef.value.innerHTML
  if (newHtml && newHtml !== currentHtml) {
    editorRef.value.innerHTML = newHtml
    syncHasContent()
    autoResize()
  } else if (!newHtml && currentHtml) {
    editorRef.value.innerHTML = ''
    hasContent.value = false
    autoResize()
  }
})

function onDocClick(e: MouseEvent) {
  if (!wrapperRef.value?.contains(e.target as Node)) {
    dismissMentionPicker()
  }
}

onMounted(() => {
  document.addEventListener('mousedown', onDocClick)
  if (editorRef.value) {
    const html = props.htmlDraft || (props.modelValue || '')
    if (html) {
      editorRef.value.innerHTML = html
      syncHasContent()
      autoResize()
    }
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
