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
  agentRole?: string // e.g., 'Host', 'Processing', 'Idle'
  agentRoleColor?: 'brand' | 'warning' | 'success' | 'error'
  content: string
  codeBlock?: {
    filename: string
    language: string
    code: string
    oldCode?: string  // Original code for diff view
    diff?: { added: number; removed: number }  // Stats only, actual diff computed from code/oldCode
  }
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