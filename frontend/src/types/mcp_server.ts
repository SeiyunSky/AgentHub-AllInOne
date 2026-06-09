export type MCPTransport = 'stdio' | 'sse'

export interface MCPServer {
  id: string
  name: string
  description?: string
  transport: MCPTransport
  command?: string
  args: string[]
  env: Record<string, string>
  url?: string
  headers: Record<string, string>
  authorId: string
  isPublic: boolean
  isActive: boolean
  createdAt: string
  updatedAt: string
}

export interface MCPServerDraft {
  name: string
  description?: string
  transport: MCPTransport
  command?: string
  args: string[]
  env: Record<string, string>
  url?: string
  headers: Record<string, string>
  isPublic: boolean
  isActive: boolean
}

export interface MCPServerCreate {
  name: string
  description?: string
  transport: MCPTransport
  command?: string
  args?: string[]
  env?: Record<string, string>
  url?: string
  headers?: Record<string, string>
  is_public?: boolean
}

export interface MCPServerUpdate {
  name?: string
  description?: string
  transport?: MCPTransport
  command?: string
  args?: string[]
  env?: Record<string, string>
  url?: string
  headers?: Record<string, string>
  is_public?: boolean
  is_active?: boolean
}

export interface MCPTestResult {
  server_id: string
  ok: boolean
  tools: string[]
  error?: string
}
