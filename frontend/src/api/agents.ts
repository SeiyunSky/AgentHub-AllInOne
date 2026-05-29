import { http } from './http'

export interface AgentCapabilities {
  supports_code: boolean
  supports_diff: boolean
  supports_approval: boolean
  supports_image: boolean
}

export interface AgentResponse {
  id: string
  user_id: string
  name: string
  description?: string
  avatar?: string
  type: string
  system_prompt?: string
  capabilities: AgentCapabilities
  tags: string[]
  is_public: boolean
  is_active: boolean
  skill_ids: string[]
  created_at: string
  updated_at: string
}

export interface AgentCreate {
  name: string
  description?: string
  avatar?: string
  type: string
  system_prompt?: string
  capabilities?: AgentCapabilities
  tags?: string[]
  is_public?: boolean
  skill_ids?: string[]
}

export interface AgentUpdate {
  name?: string
  description?: string
  avatar?: string
  system_prompt?: string
  capabilities?: AgentCapabilities
  tags?: string[]
  is_public?: boolean
  is_active?: boolean
  skill_ids?: string[]
}

export interface AgentBuildDraft {
  name: string
  description?: string
  avatar?: string
  type: string
  system_prompt: string
  capabilities?: AgentCapabilities
  tags?: string[]
  suggested_skill_names?: string[]
}

export const agentsApi = {
  list(): Promise<AgentResponse[]> {
    return http.get('/agents')
  },

  get(id: string): Promise<AgentResponse> {
    return http.get(`/agents/${id}`)
  },

  create(data: AgentCreate): Promise<AgentResponse> {
    return http.post('/agents', data)
  },

  update(id: string, data: AgentUpdate): Promise<AgentResponse> {
    return http.patch(`/agents/${id}`, data)
  },

  deactivate(id: string): Promise<AgentResponse> {
    return http.post(`/agents/${id}/deactivate`, {})
  },

  build(description: string): Promise<{ session_id: string; draft: AgentBuildDraft }> {
    return http.post('/agents/build', { description })
  },

  buildConfirm(sessionId: string, editedDraft: AgentBuildDraft): Promise<AgentResponse> {
    return http.post('/agents/build/confirm', { session_id: sessionId, edited_draft: editedDraft })
  },
}
