import { computed } from 'vue'
import DOMPurify from 'dompurify'
import { useUIStore } from '@/stores/ui'
import type { ArtifactItem } from '@/types/artifact'

export type RendererType = 'iframe' | 'svg' | 'image' | 'code' | 'unknown'

export function useArtifactPreview() {
  const uiStore = useUIStore()

  const activeArtifact = computed(() => uiStore.activeArtifact)

  const rendererType = computed<RendererType>(() => {
    const item = activeArtifact.value?.item
    if (!item) return 'unknown'

    const t = (item.mimeType ?? item.type).toLowerCase()

    if (t === 'text/html' || t === 'html') return 'iframe'
    if (t === 'image/svg+xml' || t === 'svg') return 'svg'
    if (t.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(t)) return 'image'
    if (['code', 'python', 'javascript', 'typescript', 'json', 'text/plain', 'text'].includes(t)) return 'code'
    return 'unknown'
  })

  const sanitizedSvg = computed(() => {
    if (rendererType.value !== 'svg') return ''
    const raw = activeArtifact.value?.item.preview ?? ''
    return DOMPurify.sanitize(raw, {
      USE_PROFILES: { svg: true, svgFilters: true },
      FORBID_TAGS: ['script', 'style', 'embed', 'object', 'link'],
      FORBID_ATTR: ['onload', 'onerror', 'onclick', 'onmouseover'],
    })
  })

  const iframeSrcdoc = computed(() => {
    if (rendererType.value !== 'iframe') return ''
    const raw = activeArtifact.value?.item.preview ?? ''
    const trimmed = raw.trim().toLowerCase()
    if (trimmed.startsWith('<!doctype') || trimmed.startsWith('<html')) {
      return raw
    }
    return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{margin:0;font-family:system-ui,sans-serif;}</style></head><body>${raw}</body></html>`
  })

  function openArtifact(messageId: string, item: ArtifactItem, itemIndex: number) {
    uiStore.openArtifact(messageId, item, itemIndex)
  }

  function closeArtifact() {
    uiStore.closeArtifact()
  }

  function setMode(mode: 'preview' | 'code') {
    uiStore.setPreviewMode(mode)
  }

  return {
    activeArtifact,
    rendererType,
    sanitizedSvg,
    iframeSrcdoc,
    openArtifact,
    closeArtifact,
    setMode,
  }
}
