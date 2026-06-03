<template>
  <div class="code-block rounded-xl overflow-hidden">
    <!-- Monaco Diff 视图（有 oldCode 时） -->
    <div v-if="oldCode" :style="{ height: diffHeight + 'px' }">
      <VueMonacoDiffEditor
        :original="oldCode"
        :modified="editableCode"
        :language="monacoLanguage"
        :options="diffOptions"
        @mount="onDiffEditorMount"
      />
    </div>

    <!-- Shiki 高亮视图 -->
    <template v-else-if="highlightedHtml">
      <div class="code-highlighted bg-[#f6f8fa] text-xs font-mono leading-[1.6] px-4 py-3" v-html="highlightedHtml"></div>
    </template>

    <!-- 纯文本回退 -->
    <template v-else>
      <pre class="bg-[#f6f8fa] text-xs font-mono leading-[1.6] px-4 py-3 whitespace-pre text-neutral-700">{{ code }}</pre>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { VueMonacoDiffEditor } from '@guolao/vue-monaco-editor'
import { highlightCode, initHighlighter } from '@/utils/markdown'
import { copyToClipboard } from '@/utils/clipboard'

const props = defineProps<{
  code: string
  filename?: string
  language?: string
  oldCode?: string
}>()

const emit = defineEmits<{
  'update:code': [value: string]
}>()

// 右侧可编辑内容，初始值为 props.code
const editableCode = ref(props.code)
watch(() => props.code, val => { editableCode.value = val })

// Monaco 语言 ID 映射
const LANGUAGE_MAP: Record<string, string> = {
  py: 'python', python: 'python',
  ts: 'typescript', typescript: 'typescript',
  tsx: 'typescript',
  js: 'javascript', javascript: 'javascript',
  jsx: 'javascript',
  vue: 'html',
  md: 'markdown', markdown: 'markdown',
  json: 'json',
  yaml: 'yaml', yml: 'yaml',
  sh: 'shell', bash: 'shell',
  html: 'html',
  css: 'css',
  go: 'go',
  rs: 'rust', rust: 'rust',
  java: 'java',
  kt: 'kotlin',
  swift: 'swift',
  cpp: 'cpp', c: 'c',
  sql: 'sql',
}

const monacoLanguage = computed(() => {
  if (props.language) return LANGUAGE_MAP[props.language] ?? props.language
  if (props.filename) {
    const ext = props.filename.split('.').pop()?.toLowerCase() ?? ''
    return LANGUAGE_MAP[ext] ?? ext
  }
  return 'plaintext'
})

// 行数动态高度（最小 200，最大 600）
const diffHeight = computed(() => {
  if (!props.oldCode) return 0
  const lineCount = Math.max(
    (props.oldCode ?? '').split('\n').length,
    props.code.split('\n').length,
  )
  return Math.max(200, Math.min(600, lineCount * 20 + 48))
})

const diffOptions = {
  renderSideBySide: true,
  readOnly: false,
  originalEditable: false,
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  fontSize: 12,
  lineHeight: 20,
  lineNumbers: 'on' as const,
  renderOverviewRuler: false,
  scrollbar: { verticalScrollbarSize: 6, horizontalScrollbarSize: 6 },
}

function onDiffEditorMount(diffEditor: { getModifiedEditor(): { getValue(): string; onDidChangeModelContent(cb: () => void): void } }) {
  const modifiedEditor = diffEditor.getModifiedEditor()
  modifiedEditor.onDidChangeModelContent(() => {
    const val = modifiedEditor.getValue()
    editableCode.value = val
    emit('update:code', val)
  })
}

// Shiki 高亮（无 oldCode 时）
const highlightedHtml = ref('')
const highlighterReady = ref(false)
initHighlighter().then(() => { highlighterReady.value = true })

watch(
  [() => props.code, highlighterReady],
  () => {
    if (!highlighterReady.value || props.oldCode || !props.language || !props.code) return
    highlightedHtml.value = highlightCode(props.code, props.language)
  },
  { immediate: true },
)

// Copy 暴露给 CodeBlockWrapper
const copied = ref(false)
async function handleCopy() {
  await copyToClipboard(editableCode.value)
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}
defineExpose({ handleCopy, copied, editableCode })
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
