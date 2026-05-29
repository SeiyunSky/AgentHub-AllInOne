// Legacy frontend message types for UI rendering
// These extend the API types with UI-specific fields like agentRole, agentRoleColor

import type { ContentBlock } from './api'

// UI-specific message types for chat display

export interface MessageBase {
  id: string
  timestamp: Date
  reaction?: 'like' | 'dislike'
}

export interface UserMessage extends MessageBase {
  type: 'user'
  content: string
  replyToId?: string
  mentions?: string[]
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

// Agent context for chat
export interface ChatAgent {
  id: string
  name: string
  role: string
  status: 'idle' | 'processing' | 'active' | 'error'
}

// Reply preview for input
export interface ReplyPreview {
  messageId: string
  senderName: string
  content: string
}