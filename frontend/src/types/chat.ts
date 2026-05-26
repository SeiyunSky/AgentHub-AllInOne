// Chat types — aligned with backend schemas/chat.py

import type { SelectedRange } from './api'

export interface ChatRequest {
  conversation_id: string
  content: string
  mention_ids?: string[]
  selected_range?: SelectedRange
}

export interface ChatStopRequest {
  conversation_id: string
}

export interface ChatStartedResponse {
  status: 'started'
  conversation_id: string
  user_message_id: string
}

export interface ChatQueuedResponse {
  status: 'queued'
  conversation_id: string
  queued_message_id: string
  queue_position: number
}

export type ChatResponse = ChatStartedResponse | ChatQueuedResponse

export interface ChatStopResponse {
  conversation_id: string
  aborted: boolean
  cancelled_thread_ids: string[]
  timestamp: string
}