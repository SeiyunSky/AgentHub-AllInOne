// Chat types — aligned with backend schemas/chat.py

import type { SelectedRange } from './api'

// ── API request/response types ──

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

// ── UI-facing types ──

export interface ChatAgent {
  id: string
  name: string
  role: string
  status: 'active' | 'processing' | 'idle' | 'error'
  avatar?: string
}

export interface ReplyPreview {
  messageId: string
  senderName: string
  content: string
}

// UI content blocks (camelCase, used by components)
export interface UITextBlock { type: 'text'; content: string }
export interface UIThinkingBlock { type: 'thinking'; content: string; duration?: number }
export interface UIToolUseBlock { type: 'tool_use'; toolName: string; input?: Record<string, unknown>; output?: string; status: 'running' | 'completed' | 'error' }
export interface UICodeBlock { type: 'code'; code: string; filename?: string; language?: string; oldCode?: string }
export interface UIDeploymentBlock { type: 'deployment'; title: string; status: 'deploying' | 'completed' | 'error'; url?: string; logs?: string; progress?: number }
export interface UIImageBlock { type: 'image'; src: string; alt?: string; caption?: string }
export interface UIArtifactsBlock { type: 'artifacts'; item: { name: string; type: string; preview?: string } }
export interface UIApprovalBlock { type: 'approval'; blockId: string; action: string; detail: string; status: 'pending' | 'approved' | 'rejected'; decidedAt?: string; rejectReason?: string }

export type UIBlock =
  | UITextBlock | UIThinkingBlock | UIToolUseBlock | UICodeBlock
  | UIDeploymentBlock | UIImageBlock | UIArtifactsBlock | UIApprovalBlock

export interface AgentMessage {
  id: string
  type: 'agent'
  agentId: string
  agentName: string
  agentRole?: string
  agentRoleColor?: string
  avatar?: string
  content: string
  timestamp: Date
  blocks?: UIBlock[]
  reaction?: 'like' | 'dislike'
  model?: string
  sender?: string
  tokensInput?: number
  tokensOutput?: number
  latencyMs?: number
}

export interface UserMessage {
  id: string
  type: 'user'
  content: string
  timestamp: Date
  reaction?: 'like' | 'dislike'
}

export interface TypingMessage {
  id: string
  type: 'typing'
  agentId: string
  agentName: string
  timestamp: Date
}

export type Message = AgentMessage | UserMessage | TypingMessage