import { http } from './http'
import type { MCPServerCreate, MCPServerUpdate, MCPTestResult } from '@/types/mcp_server'

export interface MCPServerResponse {
  id: string
  name: string
  description?: string
  transport: 'stdio' | 'sse' | 'streamable_http'
  command?: string
  args: string[]
  env: Record<string, string>
  url?: string
  headers: Record<string, string>
  author_id: string
  is_public: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export const mcpServersApi = {
  list(): Promise<MCPServerResponse[]> {
    return http.get('/mcp-servers')
  },

  get(id: string): Promise<MCPServerResponse> {
    return http.get(`/mcp-servers/${id}`)
  },

  create(data: MCPServerCreate): Promise<MCPServerResponse> {
    return http.post('/mcp-servers', data)
  },

  update(id: string, data: MCPServerUpdate): Promise<MCPServerResponse> {
    return http.patch(`/mcp-servers/${id}`, data)
  },

  remove(id: string): Promise<void> {
    return http.delete(`/mcp-servers/${id}`)
  },

  test(id: string): Promise<MCPTestResult> {
    return http.post(`/mcp-servers/${id}/test`, {})
  },

  // Agent 挂载管理
  listForAgent(agentId: string): Promise<MCPServerResponse[]> {
    return http.get(`/agents/${agentId}/mcp-servers`)
  },

  attach(agentId: string, mcpServerId: string): Promise<MCPServerResponse> {
    return http.post(`/agents/${agentId}/mcp-servers/${mcpServerId}`, {})
  },

  detach(agentId: string, mcpServerId: string): Promise<void> {
    return http.delete(`/agents/${agentId}/mcp-servers/${mcpServerId}`)
  },
}
