import { http } from './http'
import type { MessageResponse } from '@/types/api'

export const messagesApi = {
  get(messageId: string): Promise<MessageResponse> {
    return http.get(`/messages/${messageId}`)
  },

  list(conversationId: string, params?: {
    limit?: number
    before?: string
  }): Promise<MessageResponse[]> {
    return http.get(`/conversations/${conversationId}/messages`, { params })
  },

  updateFeedback(messageId: string, feedback: 'up' | 'down' | null): Promise<MessageResponse> {
    return http.post(`/messages/${messageId}/feedback`, { feedback })
  },
}
