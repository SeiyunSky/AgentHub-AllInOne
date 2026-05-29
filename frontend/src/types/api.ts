// Unified API response envelope — aligned with backend schemas/response.py
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T | null
}

// Content block types — aligned with backend domain/message.py

export interface TextBlock {
  block_id: string
  type: 'text'
  content: string
}

export interface ThinkingBlock {
  block_id: string
  type: 'thinking'
  content: string
  duration_ms?: number
}

export type ToolUseStatus = 'running' | 'completed' | 'error'

export interface ToolUseBlock {
  block_id: string
  type: 'tool_use'
  tool_name: string
  input?: Record<string, unknown>
  output?: string
  status: ToolUseStatus
  error_message?: string
}

export interface CodeBlock {
  block_id: string
  type: 'code'
  language: string
  code: string
  filename?: string
  old_code?: string
  additions?: number
  deletions?: number
  applied_commit_hash?: string
}

export type ApprovalStatus = 'pending' | 'approved' | 'rejected'

export interface ApprovalBlock {
  block_id: string
  type: 'approval'
  action: string
  detail: string
  status: ApprovalStatus
  decided_at?: string
  reject_reason?: string
}

export type DeploymentStatus = 'deploying' | 'completed' | 'error'

export interface DeploymentBlock {
  block_id: string
  type: 'deployment'
  title: string
  status: DeploymentStatus
  progress?: number
  url?: string
  logs?: string
}

export interface ImageBlock {
  block_id: string
  type: 'image'
  src: string
  alt?: string
  caption?: string
}

export interface ArtifactItem {
  name: string
  type: string
  preview?: string
}

export interface ArtifactsBlock {
  block_id: string
  type: 'artifacts'
  title: string
  items: ArtifactItem[]
}

export type ContentBlock =
  | TextBlock
  | ThinkingBlock
  | ToolUseBlock
  | CodeBlock
  | ApprovalBlock
  | DeploymentBlock
  | ImageBlock
  | ArtifactsBlock

// Message types — aligned with backend schemas/message.py

export type MessageRole = 'user' | 'assistant'
export type MessageStatus = 'streaming' | 'done' | 'error'
export type MessageFeedback = 'up' | 'down'

export interface SelectedRange {
  file: string
  start: number
  end: number
  code: string
}

export interface MessageResponse {
  id: string
  conversation_id: string
  thread_id?: string
  parent_id?: string
  user_id?: string
  agent_id?: string
  role: MessageRole
  blocks: ContentBlock[]
  status: MessageStatus
  error_message?: string
  model?: string
  sender?: string
  tokens_input?: number
  tokens_output?: number
  latency_ms?: number
  feedback?: MessageFeedback
  selected_range?: SelectedRange
  is_deleted: boolean
  created_at: string
}

// SSE event types — aligned with backend adapters/events.py

export interface AgentStartEvent {
  type: 'agent_start'
  agent_id: string
  thread_id: string
  message_id: string
  agent_name: string
  timestamp: string
}

export interface BlockStartEvent {
  type: 'block_start'
  agent_id: string
  thread_id: string
  message_id: string
  block: ContentBlock
  timestamp: string
}

export interface BlockDeltaEvent {
  type: 'block_delta'
  agent_id: string
  thread_id: string
  message_id: string
  block_id: string
  delta: Record<string, unknown>
  timestamp: string
}

export interface BlockStopEvent {
  type: 'block_stop'
  agent_id: string
  thread_id: string
  message_id: string
  block_id: string
  final_fields?: Record<string, unknown>
  timestamp: string
}

export interface AgentDoneEvent {
  type: 'agent_done'
  agent_id: string
  thread_id: string
  message_id: string
  tokens_input?: number
  tokens_output?: number
  timestamp: string
}

export interface AgentErrorEvent {
  type: 'agent_error'
  agent_id: string
  thread_id: string
  message_id: string
  error: string
  timestamp: string
}

export interface RoundDoneEvent {
  type: 'round_done'
  timestamp: string
}

export interface QueueDrainedEvent {
  type: 'queue_drained'
  timestamp: string
}

export type AgentEvent =
  | AgentStartEvent
  | BlockStartEvent
  | BlockDeltaEvent
  | BlockStopEvent
  | AgentDoneEvent
  | AgentErrorEvent

export type SSEEvent = AgentEvent | RoundDoneEvent | QueueDrainedEvent
