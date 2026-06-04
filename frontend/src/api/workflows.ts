import { http } from './http'

export interface WorkflowBlockDTO {
  blockId: string
  type: string
  toolName?: string
  toolInput?: Record<string, unknown>
  content?: string
  language?: string
  code?: string
  filename?: string
  status: string
  startedAt?: number
  finishedAt?: number
}

export interface WorkflowThreadDTO {
  threadId: string
  agentId: string
  agentName: string
  messageId: string
  status: string
  blocks: WorkflowBlockDTO[]
  startedAt?: number
  finishedAt?: number
  error?: string
  tokensInput?: number
  tokensOutput?: number
}

export interface WorkflowResponse {
  id: string
  conversation_id: string
  user_id: string
  trigger_message_id?: string
  threads: WorkflowThreadDTO[]
  created_at: string
}

export interface WorkflowCreatePayload {
  conversation_id: string
  trigger_message_id?: string
  threads: WorkflowThreadDTO[]
}

export const workflowsApi = {
  save(payload: WorkflowCreatePayload): Promise<WorkflowResponse> {
    return http.post('/workflows', payload)
  },
  list(conversationId: string, params?: { limit?: number; offset?: number }): Promise<WorkflowResponse[]> {
    return http.get('/workflows', {
      params: { conversation_id: conversationId, ...params },
    })
  },
}
