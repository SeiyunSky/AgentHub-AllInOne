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

    <!-- Shiki 高亮视图(超过阈值行数时支持折叠) -->
    <template v-else-if="highlightedHtml">
      <div class="relative">
        <div
          class="code-highlighted bg-[#f6f8fa] text-xs font-mono leading-[1.6] px-4 py-3 transition-[max-height] duration-200"
          :class="needsCollapse && !fullyExpanded ? 'overflow-hidden' : 'overflow-x-auto'"
          :style="needsCollapse && !fullyExpanded ? { maxHeight: collapsedMaxHeight + 'px' } : {}"
          v-html="highlightedHtml"
        ></div>
        <!-- 渐变蒙层 + 展开按钮 -->
        <div
          v-if="needsCollapse && !fullyExpanded"
          class="absolute inset-x-0 bottom-0 h-12 pointer-events-none bg-gradient-to-t from-[#f6f8fa] via-[#f6f8fa]/80 to-transparent"
        ></div>
        <button
          v-if="needsCollapse"
          class="w-full text-[11px] text-brand hover:text-brand-dark hover:bg-brand-light/30 transition-colors py-1.5 border-t border-outline-variant cursor-pointer flex items-center justify-center gap-1"
          @click.stop="fullyExpanded = !fullyExpanded"
        >
          {{ fullyExpanded ? t('codeBlock.collapseLines', { n: lineCount }) : t('codeBlock.showAllLines', { n: lineCount }) }}
        </button>
      </div>
    </template>

    <!-- 纯文本回退(同样支持折叠) -->
    <template v-else>
      <div class="relative">
        <pre
          class="bg-[#f6f8fa] text-xs font-mono leading-[1.6] px-4 py-3 whitespace-pre text-neutral-700 transition-[max-height] duration-200"
          :class="needsCollapse && !fullyExpanded ? 'overflow-hidden' : 'overflow-x-auto'"
          :style="needsCollapse && !fullyExpanded ? { maxHeight: collapsedMaxHeight + 'px' } : {}"
        >{{ code }}</pre>
        <div
          v-if="needsCollapse && !fullyExpanded"
          class="absolute inset-x-0 bottom-0 h-12 pointer-events-none bg-gradient-to-t from-[#f6f8fa] via-[#f6f8fa]/80 to-transparent"
        ></div>
        <button
          v-if="needsCollapse"
          class="w-full text-[11px] text-brand hover:text-brand-dark hover:bg-brand-light/30 transition-colors py-1.5 border-t border-outline-variant cursor-pointer flex items-center justify-center gap-1"
          @click.stop="fullyExpanded = !fullyExpanded"
        >
          {{ fullyExpanded ? t('codeBlock.collapseLines', { n: lineCount }) : t('codeBlock.showAllLines', { n: lineCount }) }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
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

const { t } = useI18n()

// 右侧可编辑内容，初始值为 props.code
const editableCode = ref(props.code)
watch(() => props.code, val => { editableCode.value = val })

// 长代码块默认折叠到 ~12 行(约 240px),避免聊天最后一条是大代码块时
// 把视口撑到看不到上下文。点底部按钮再展开全部。
const _LINE_THRESHOLD = 12
const collapsedMaxHeight = 240
const fullyExpanded = ref(false)
const lineCount = computed(() => (props.code ?? '').split('\n').length)
const needsCollapse = computed(() => lineCount.value > _LINE_THRESHOLD)

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
