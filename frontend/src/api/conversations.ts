import { http } from './http'
import type { MessageResponse } from '@/types/api'
import type {
  ConversationCreate,
  ConversationUpdate,
  ConversationListItem,
  ConversationResponse,
} from '@/types/conversation'

export interface TokenUsageByAgent {
  agent_id: string
  agent_name: string
  tokens_input: number
  tokens_output: number
  messages_count: number
}

export interface ConversationTokenUsage {
  conversation_id: string
  by_agent: TokenUsageByAgent[]
  total: { tokens_input: number; tokens_output: number }
}

export const conversationsApi = {
  create(data: ConversationCreate): Promise<ConversationResponse> {
    return http.post('/conversations', data)
  },

  list(params?: { include_archived?: boolean; limit?: number; offset?: number }): Promise<ConversationListItem[]> {
    return http.get('/conversations', { params })
  },

  get(id: string): Promise<ConversationResponse> {
    return http.get(`/conversations/${id}`)
  },

  update(id: string, data: ConversationUpdate): Promise<ConversationResponse> {
    return http.patch(`/conversations/${id}`, data)
  },

  messages(
    id: string,
    params?: { limit?: number; before?: string },
  ): Promise<MessageResponse[]> {
    return http.get(`/conversations/${id}/messages`, { params })
  },

  /** 删除会话 */
  delete(id: string): Promise<void> {
    return http.delete(`/conversations/${id}`)
  },

  /** 把 Agent 加入会话(群聊) */
  addAgent(conversationId: string, agentId: string): Promise<ConversationResponse> {
    return http.post(`/conversations/${conversationId}/agents`, { agent_id: agentId })
  },

  /** 把 Agent 从会话踢掉(群聊) */
  removeAgent(conversationId: string, agentId: string): Promise<ConversationResponse> {
    return http.delete(`/conversations/${conversationId}/agents/${agentId}`)
  },

  /** 会话 token 用量统计 */
  tokenUsage(conversationId: string): Promise<ConversationTokenUsage> {
    return http.get(`/conversations/${conversationId}/token_usage`)
  },
}
