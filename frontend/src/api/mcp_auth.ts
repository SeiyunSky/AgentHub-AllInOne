import { http } from './http'

export interface MCPAuthStartResponse {
  status: 'authorized' | 'pending' | 'error' | 'unknown'
  server_id: string
  auth_url?: string
  message?: string
}

export interface MCPAuthStatusResponse {
  server_id: string
  authorized: boolean
  expires_at?: string | null
  mode?: string
}

export const mcpAuthApi = {
  start(serverId: string): Promise<MCPAuthStartResponse> {
    return http.get(`/mcp-auth/${serverId}/start`)
  },
  status(serverId: string): Promise<MCPAuthStatusResponse> {
    return http.get(`/mcp-auth/status/${serverId}`)
  },
}

/** SAP OIDC 需要授权的服务器 ID 集合（Client Credentials 自动完成，不需要用户操作） */
export const SAP_OIDC_SERVER_IDS = new Set([
  'l2a-globalization-taxonomy',
  'l2a-solution-patterns',
  'l2a-test-case-creator',
])

/** 是否是需要用户 OIDC 授权的 SAP MCP */
export function isSapOidcServer(serverId: string): boolean {
  return SAP_OIDC_SERVER_IDS.has(serverId)
}
