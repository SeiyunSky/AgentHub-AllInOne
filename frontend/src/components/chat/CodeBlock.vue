<template>
  <div class="code-block rounded-xl overflow-hidden">
    <!-- Code content -->
    <div class="bg-[#f6f8fa] text-xs font-mono leading-[1.6] overflow-x-auto">
      <!-- Diff view -->
      <template v-if="diffLines.length > 0">
        <div
          v-for="(line, i) in diffLines"
          :key="i"
          class="flex items-stretch"
          :class="lineClass(line.type)"
        >
          <span class="w-8 text-right px-2 text-neutral-400 select-none shrink-0 bg-neutral-100/50" :class="{ 'opacity-50': line.type === 'added' }">
            {{ line.oldNum ?? '' }}
          </span>
          <span class="w-8 text-right px-2 text-neutral-400 select-none shrink-0 border-l border-neutral-200" :class="{ 'opacity-50': line.type === 'removed' }">
            {{ line.newNum ?? '' }}
          </span>
          <span class="w-5 text-center select-none shrink-0" :class="markerClass(line.type)">
            {{ line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' ' }}
          </span>
          <pre class="px-2 flex-1 whitespace-pre" :class="contentClass(line.type)">{{ line.content }}</pre>
        </div>
      </template>

      <!-- Highlighted code view (shiki) -->
      <template v-else-if="highlightedHtml">
        <div class="code-highlighted px-4 py-3" v-html="highlightedHtml"></div>
      </template>

      <!-- Fallback: plain code view -->
      <template v-else>
        <div
          v-for="(line, i) in codeLines"
          :key="i"
          class="flex items-stretch hover:bg-neutral-200/50"
        >
          <span class="w-8 text-right px-2 text-neutral-600 select-none shrink-0">{{ i + 1 }}</span>
          <span class="w-5 text-center text-neutral-300 select-none shrink-0">│</span>
          <pre class="px-2 flex-1 whitespace-pre text-neutral-700">{{ line }}</pre>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import * as Diff from 'diff'
import { highlightCode, initHighlighter } from '@/utils/markdown'

const props = defineProps<{
  code: string
  filename?: string
  language?: string
  oldCode?: string
}>()

const codeLines = computed(() => props.code.split('\n'))

const highlightedHtml = ref('')

onMounted(async () => {
  await initHighlighter()
  if (!props.oldCode && props.language) {
    highlightedHtml.value = highlightCode(props.code, props.language)
  }
})

const diffLines = computed(() => {
  if (!props.oldCode) return []

  const patch = Diff.createPatch('', props.oldCode, props.code, '', '')
  const patchLines = patch.split('\n').slice(4)

  let oldNum = 0
  let newNum = 0
  const result: Array<{
    type: 'added' | 'removed' | 'context'
    content: string
    oldNum?: number
    newNum?: number
  }> = []

  for (const line of patchLines) {
    if (line.startsWith('@@')) {
      const match = line.match(/@@ -(\d+),?\d* \+(\d+),?\d* @@/)
      if (match) {
        oldNum = parseInt(match[1])
        newNum = parseInt(match[2])
      }
      continue
    }

    if (line.startsWith('+')) {
      result.push({ type: 'added', content: line.slice(1), newNum })
      newNum++
    } else if (line.startsWith('-')) {
      result.push({ type: 'removed', content: line.slice(1), oldNum })
      oldNum++
    } else if (line.startsWith(' ')) {
      result.push({ type: 'context', content: line.slice(1), oldNum, newNum })
      oldNum++
      newNum++
    }
  }

  return result
})

function lineClass(type: string) {
  switch (type) {
    case 'added': return 'bg-emerald-50'
    case 'removed': return 'bg-red-50'
    default: return ''
  }
}

function markerClass(type: string) {
  switch (type) {
    case 'added': return 'text-emerald-600'
    case 'removed': return 'text-red-600'
    default: return 'text-neutral-700'
  }
}

function contentClass(type: string) {
  switch (type) {
    case 'added': return 'text-emerald-700'
    case 'removed': return 'text-red-700'
    default: return 'text-neutral-700'
  }
}

const copied = ref(false)

async function handleCopy() {
  try {
    await navigator.clipboard.writeText(props.code)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = props.code
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}

defineExpose({ handleCopy, copied })
</script>

<style scoped>
.code-highlighted :deep(pre) {
  margin: 0;
  padding: 0;
  background: transparent !important;
  font-size: inherit;
  line-height: inherit;
}

.code-highlighted :deep(code) {
  font-family: inherit;
  font-size: inherit;
  line-height: inherit;
}
</style>
