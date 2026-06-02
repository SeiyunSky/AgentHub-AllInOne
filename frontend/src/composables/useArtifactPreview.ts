import { computed, ref } from 'vue'
import DOMPurify from 'dompurify'
import { useUIStore } from '@/stores/ui'
import { filesApi } from '@/api/files'
import type { ArtifactItem } from '@/types/artifact'

export type RendererType = 'iframe' | 'svg' | 'image' | 'code' | 'unknown'

// Module-level singletons so all useArtifactPreview() callers share the same state
// null = file not yet loaded from server; string = loaded (including empty string)
const editContent = ref<string | null>(null)
const isSaving = ref(false)
const isLoadingContent = ref(false)

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

  // editContent (when loaded) takes priority over item.preview so preview stays in sync after edits
  const liveContent = computed(() =>
    editContent.value !== null ? editContent.value : (activeArtifact.value?.item.preview ?? '')
  )

  const sanitizedSvg = computed(() => {
    if (rendererType.value !== 'svg') return ''
    return DOMPurify.sanitize(liveContent.value, {
      USE_PROFILES: { svg: true, svgFilters: true },
      FORBID_TAGS: ['script', 'style', 'embed', 'object', 'link'],
      FORBID_ATTR: ['onload', 'onerror', 'onclick', 'onmouseover'],
    })
  })

  const iframeSrcdoc = computed(() => {
    if (rendererType.value !== 'iframe') return ''
    const raw = liveContent.value
    const trimmed = raw.trim().toLowerCase()
    if (trimmed.startsWith('<!doctype') || trimmed.startsWith('<html')) {
      return raw
    }
    return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{margin:0;font-family:system-ui,sans-serif;}</style></head><body>${raw}</body></html>`
  })

  async function loadFileContent() {
    const filePath = activeArtifact.value?.item.filePath
    if (!filePath) return
    isLoadingContent.value = true
    editContent.value = null
    try {
      const res = await filesApi.getContent(filePath)
      editContent.value = res.content
    } finally {
      isLoadingContent.value = false
    }
  }

  async function saveFileContent() {
    const filePath = activeArtifact.value?.item.filePath
    if (!filePath || editContent.value === null) return
    isSaving.value = true
    try {
      await filesApi.saveContent(filePath, editContent.value)
    } finally {
      isSaving.value = false
    }
  }

  function openArtifact(messageId: string, item: ArtifactItem, itemIndex: number) {
    editContent.value = null
    uiStore.openArtifact(messageId, item, itemIndex)
    if (item.filePath) {
      loadFileContent()
    }
  }

  function closeArtifact() {
    uiStore.closeArtifact()
    editContent.value = null
  }

  function setMode(mode: 'preview' | 'edit') {
    uiStore.setPreviewMode(mode)
    if (mode === 'edit' && editContent.value === null) {
      loadFileContent()
    }
  }

  function setEditContent(v: string) {
    editContent.value = v
  }

  return {
    activeArtifact,
    rendererType,
    sanitizedSvg,
    iframeSrcdoc,
    liveContent,
    editContent,
    isSaving,
    isLoadingContent,
    openArtifact,
    closeArtifact,
    setMode,
    saveFileContent,
    setEditContent,
  }
}
