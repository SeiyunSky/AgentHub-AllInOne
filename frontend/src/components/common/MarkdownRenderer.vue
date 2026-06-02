<template>
  <div :class="themeClass" v-html="rendered" @click="handleClick"></div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { renderMarkdown, initHighlighter } from '@/utils/markdown'
import { copyToClipboard } from '@/utils/clipboard'

const props = withDefaults(defineProps<{
  content: string
  theme?: 'light' | 'dark'
}>(), {
  theme: 'light',
})

const ready = ref(false)
onMounted(async () => {
  await initHighlighter()
  ready.value = true
})

const rendered = computed(() => {
  if (!ready.value) return ''
  return renderMarkdown(props.content)
})

const themeClass = computed(() =>
  props.theme === 'dark' ? 'markdown-body-dark' : 'markdown-body'
)

function handleClick(e: MouseEvent) {
  const target = e.target as HTMLElement

  const copyBtn = target.closest<HTMLElement>('[data-action="copy"]')
  if (copyBtn) {
    e.stopPropagation()
    const codeId = copyBtn.dataset.target
    const el = codeId ? document.getElementById(codeId) : null
    if (el) {
      copyToClipboard(el.textContent ?? '').then(() => {
        copyBtn.textContent = 'Copied!'
        setTimeout(() => { copyBtn.textContent = 'Copy' }, 1500)
      })
    }
    return
  }

  const toggleBtn = target.closest<HTMLElement>('[data-action="toggle"]')
  if (toggleBtn) {
    const wrapperId = toggleBtn.dataset.target
    if (wrapperId) document.getElementById(wrapperId)?.classList.toggle('collapsed')
  }
}
</script>
