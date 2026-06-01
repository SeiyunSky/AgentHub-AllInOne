import { http } from './http'
import type { MessageResponse } from '@/types/api'
import type {
  ConversationCreate,
  ConversationUpdate,
  ConversationListItem,
  ConversationResponse,
} from '@/types/conversation'

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
}
