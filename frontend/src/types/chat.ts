// Content block types for agent messages

export interface TextBlock {
  type: 'text'
  content: string
}

export interface ThinkingBlock {
  type: 'thinking'
  content: string
  duration?: number
}

export interface ToolUseBlock {
  type: 'tool_use'
  toolName: string
  input?: Record<string, unknown>
  output?: string
  status: 'running' | 'completed' | 'error'
}

export interface CodeBlockData {
  type: 'code'
  code: string
  filename?: string
  language?: string
  oldCode?: string
}

export interface DeploymentBlockData {
  type: 'deployment'
  title: string
  status: 'deploying' | 'completed' | 'error'
  url?: string
  logs?: string
  progress?: number
}

export interface ImageBlockData {
  type: 'image'
  src: string
  alt?: string
  caption?: string
}

export interface ArtifactsBlockData {
  type: 'artifacts'
  title: string
  items: Array<{
    name: string
    type: string
    preview?: string
  }>
}

export type ContentBlock =
  | TextBlock
  | ThinkingBlock
  | ToolUseBlock
  | CodeBlockData
  | DeploymentBlockData
  | ImageBlockData
  | ArtifactsBlockData

// Message types for chat system

export interface MessageBase {
  id: string
  timestamp: Date
}

export interface UserMessage extends MessageBase {
  type: 'user'
  content: string
}

export interface AgentMessage extends MessageBase {
  type: 'agent'
  agentId: string
  agentName: string
  agentRole?: string
  agentRoleColor?: 'brand' | 'warning' | 'success' | 'error'
  content: string
  codeBlock?: {
    filename: string
    language: string
    code: string
    oldCode?: string
    diff?: { added: number; removed: number }
  }
  blocks?: ContentBlock[]
}

export interface TypingMessage extends MessageBase {
  type: 'typing'
  agentId: string
  agentName: string
}

export type Message = UserMessage | AgentMessage | TypingMessage

// Conversation type
export interface Conversation {
  id: string
  title: string
  messages: Message[]
  createdAt: Date
  updatedAt: Date
}

// Agent context for chat
export interface ChatAgent {
  id: string
  name: string
  role: string
  status: 'idle' | 'processing' | 'active' | 'error'
}
