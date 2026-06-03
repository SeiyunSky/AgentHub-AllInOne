import { computed, ref } from 'vue'
import DOMPurify from 'dompurify'
import { useUIStore } from '@/stores/ui'
import { filesApi } from '@/api/files'
import { sandboxApi } from '@/api/sandbox'
import type { ArtifactItem } from '@/types/artifact'

export type RendererType = 'iframe' | 'svg' | 'image' | 'markdown' | 'code' | 'unknown'

// ---- 扩展名 → 类型 / Monaco language 映射(共用,SandboxFilesView 也用) ----

const IMAGE_EXTS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'ico'])
const MARKDOWN_EXTS = new Set(['md', 'markdown'])

// 扩展名 → Monaco language id;未列出的统一回 plaintext
const EXT_TO_MONACO: Record<string, string> = {
  // web
  html: 'html', htm: 'html', vue: 'html',
  css: 'css', scss: 'scss', sass: 'scss', less: 'less',
  // js/ts
  js: 'javascript', mjs: 'javascript', cjs: 'javascript', jsx: 'javascript',
  ts: 'typescript', tsx: 'typescript',
  // popular langs
  py: 'python', rb: 'ruby', php: 'php',
  java: 'java', kt: 'kotlin', scala: 'scala', groovy: 'groovy',
  go: 'go', rs: 'rust', swift: 'swift',
  c: 'c', h: 'c',
  cpp: 'cpp', cc: 'cpp', cxx: 'cpp', hpp: 'cpp',
  cs: 'csharp',
  // shell / data
  sh: 'shell', bash: 'shell', zsh: 'shell', fish: 'shell',
  ps1: 'powershell',
  yaml: 'yaml', yml: 'yaml', toml: 'ini', ini: 'ini',
  json: 'json', json5: 'json', xml: 'xml',
  sql: 'sql',
  // docs
  md: 'markdown', markdown: 'markdown',
  // misc
  dockerfile: 'dockerfile',
}

function extOf(name: string): string {
  const idx = name.lastIndexOf('.')
  return idx === -1 ? '' : name.slice(idx + 1).toLowerCase()
}

export function monacoLangFromExt(ext: string): string {
  return EXT_TO_MONACO[ext.toLowerCase()] ?? 'plaintext'
}

export function rendererTypeFromExt(ext: string): RendererType {
  const e = ext.toLowerCase()
  if (e === 'html' || e === 'htm') return 'iframe'
  if (e === 'svg') return 'svg'
  if (IMAGE_EXTS.has(e)) return 'image'
  if (MARKDOWN_EXTS.has(e)) return 'markdown'
  // 已知文本 → code;不识别但能读出文本也走 code(plaintext fallback)
  return 'code'
}

// Module-level singletons so all useArtifactPreview() callers share the same state
// null = file not yet loaded from server; string = loaded (including empty string)
const editContent = ref<string | null>(null)
const isSaving = ref(false)
const isLoadingContent = ref(false)

export function useArtifactPreview() {
  const uiStore = useUIStore()

  const activeArtifact = computed(() => uiStore.activeArtifact)

  // 优先用 ArtifactItem.path / name 推断扩展名(沙箱场景),
  // 没有就 fallback 到 mimeType / type 字段(老路径场景)
  const fileExt = computed(() => {
    const item = activeArtifact.value?.item
    if (!item) return ''
    return extOf(item.path ?? item.name ?? '')
  })

  const rendererType = computed<RendererType>(() => {
    const item = activeArtifact.value?.item
    if (!item) return 'unknown'

    const ext = fileExt.value
    if (ext) return rendererTypeFromExt(ext)

    // 没扩展名 / 不是沙箱场景:看 mimeType / type 字段
    const t = (item.mimeType ?? item.type).toLowerCase()
    if (t === 'text/html' || t === 'html') return 'iframe'
    if (t === 'image/svg+xml' || t === 'svg') return 'svg'
    if (t.startsWith('image/')) return 'image'
    if (t === 'text/markdown' || t === 'markdown' || t === 'md') return 'markdown'
    return 'code'
  })

  const monacoLanguage = computed<string>(() => {
    const ext = fileExt.value
    if (ext) return monacoLangFromExt(ext)
    // fallback by type/mimeType for legacy artifacts
    const t = (activeArtifact.value?.item.mimeType ?? activeArtifact.value?.item.type ?? '').toLowerCase()
    if (t === 'text/html' || t === 'html') return 'html'
    if (t === 'image/svg+xml' || t === 'svg') return 'xml'
    if (t === 'application/json' || t === 'json') return 'json'
    if (t === 'python') return 'python'
    if (t === 'typescript') return 'typescript'
    if (t === 'javascript') return 'javascript'
    if (t === 'markdown' || t === 'md') return 'markdown'
    return 'plaintext'
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
    const item = activeArtifact.value?.item
    if (!item) return
    isLoadingContent.value = true
    editContent.value = null
    try {
      // 沙箱文件:有 convId 就走 sandboxApi
      if (item.convId && item.path) {
        const res = await sandboxApi.read(item.convId, item.path)
        editContent.value = res.content
        return
      }
      // 旧路径(filesApi 端点目前后端没实现,保留兼容)
      if (item.filePath) {
        const res = await filesApi.getContent(item.filePath)
        editContent.value = res.content
      }
    } finally {
      isLoadingContent.value = false
    }
  }

  async function saveFileContent() {
    const item = activeArtifact.value?.item
    if (!item || editContent.value === null) return
    isSaving.value = true
    try {
      if (item.convId && item.path) {
        await sandboxApi.save(item.convId, item.path, editContent.value)
        return
      }
      if (item.filePath) {
        await filesApi.saveContent(item.filePath, editContent.value)
      }
    } finally {
      isSaving.value = false
    }
  }

  function openArtifact(messageId: string, item: ArtifactItem, itemIndex: number) {
    editContent.value = null
    uiStore.openArtifact(messageId, item, itemIndex)
    // 沙箱文件 / 普通本地文件,只要有可加载的来源就预拉
    if (item.convId || item.filePath) {
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
    monacoLanguage,
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
