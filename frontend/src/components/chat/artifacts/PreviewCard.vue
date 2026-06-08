<template>
  <div
    v-if="item.preview"
    class="mt-2 rounded-lg border border-outline-variant overflow-hidden bg-surface-container-low"
  >
    <!-- Inline iframe for HTML -->
    <iframe
      v-if="localRendererType === 'iframe'"
      :srcdoc="item.preview"
      sandbox="allow-scripts"
      class="w-full h-40 pointer-events-none"
      loading="lazy"
    />
    <!-- Inline SVG -->
    <div
      v-else-if="localRendererType === 'svg'"
      class="w-full h-40 flex items-center justify-center p-2"
      v-html="sanitizedSvg"
    />
    <!-- Code preview snippet -->
    <div v-else-if="localRendererType === 'code'" class="w-full h-40 overflow-hidden p-2 bg-neutral-50">
      <pre class="code-snippet text-[11px] leading-tight font-mono text-neutral-600">{{ item.preview }}</pre>
    </div>

    <!-- Bottom bar -->
    <div class="px-2 py-1.5 flex items-center justify-between border-t border-outline-variant bg-white">
      <span class="text-[11px] text-on-surface-variant truncate max-w-[60%]">{{ item.name }}</span>
      <el-button
        text
        size="small"
        class="!text-[11px] !text-brand !px-1.5 !py-0.5"
        @click="onOpen"
      >
        {{ t('previewCard.fullPreview') }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import DOMPurify from 'dompurify'
import { useArtifactPreview } from '@/composables/useArtifactPreview'
import type { ArtifactItem } from '@/types/artifact'

const props = defineProps<{
  messageId: string
  item: ArtifactItem
  itemIndex: number
}>()

const { t } = useI18n()
const { openArtifact } = useArtifactPreview()

const localRendererType = computed(() => {
  const t = (props.item.mimeType ?? props.item.type).toLowerCase()
  if (t === 'text/html' || t === 'html') return 'iframe'
  if (t === 'image/svg+xml' || t === 'svg') return 'svg'
  if (['code', 'python', 'javascript', 'typescript', 'json', 'text/plain', 'text'].includes(t)) return 'code'
  return 'unknown'
})

const sanitizedSvg = computed(() => {
  if (localRendererType.value !== 'svg') return ''
  return DOMPurify.sanitize(props.item.preview ?? '', {
    USE_PROFILES: { svg: true, svgFilters: true },
    FORBID_TAGS: ['script', 'style', 'embed', 'object', 'link'],
    FORBID_ATTR: ['onload', 'onerror', 'onclick', 'onmouseover'],
  })
})

function onOpen() {
  openArtifact(props.messageId, props.item, props.itemIndex)
}
</script>

<style scoped>
.code-snippet {
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 6;
  -webkit-box-orient: vertical;
}
</style>
