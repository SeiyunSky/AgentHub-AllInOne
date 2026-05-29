export type ArtifactKind = 'text/html' | 'image/svg+xml' | 'text/plain' | 'application/json' | 'image/*'

export interface ArtifactItem {
  name: string
  type: string
  preview?: string
  mimeType?: ArtifactKind
}

export interface ActiveArtifact {
  id: string
  messageId: string
  item: ArtifactItem
  mode: 'preview' | 'code'
}
