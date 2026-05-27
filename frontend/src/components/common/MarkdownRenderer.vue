<template>
  <div :class="themeClass" v-html="rendered"></div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { renderMarkdown, initHighlighter } from '@/utils/markdown'

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
</script>
