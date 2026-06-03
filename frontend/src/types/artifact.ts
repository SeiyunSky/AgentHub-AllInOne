export type ArtifactKind = 'text/html' | 'image/svg+xml' | 'text/plain' | 'application/json' | 'image/*'

export interface ArtifactItem {
  name: string
  type: string
  preview?: string
  mimeType?: ArtifactKind
  filePath?: string  // local file path; present = edit tab enabled
  // 沙箱文件场景:convId + path 让 useArtifactPreview 走 sandboxApi 而不是 filesApi
  convId?: string
  path?: string      // 相对沙箱根的 POSIX 路径(沙箱预览专用)
}

export interface ActiveArtifact {
  id: string
  messageId: string
  item: ArtifactItem
  mode: 'preview' | 'edit'
}
