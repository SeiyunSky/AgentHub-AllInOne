import { http } from './http'
import { connectSSE } from './sse'
import type { SSEEvent } from '@/types/api'
import type { ChatRequest, ChatResponse, ChatStopRequest, ChatStopResponse } from '@/types/chat'

export const chatApi = {
  send(data: ChatRequest): Promise<ChatResponse> {
    return http.post('/chat', data)
  },

  stop(data: ChatStopRequest): Promise<ChatStopResponse> {
    return http.post('/chat/stop', data)
  },

  stream(
    conversationId: string,
    handlers: {
      onEvent: (event: SSEEvent) => void
      onError?: (error: Error) => void
      onClose?: () => void
    },
  ): AbortController {
    return connectSSE(`/api/v1/chat/stream/${conversationId}`, {
      onEvent: handlers.onEvent,
      onError: handlers.onError,
      onClose: handlers.onClose,
    })
  },
}
