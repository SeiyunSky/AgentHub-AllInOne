// Conversation types — aligned with backend schemas/conversation.py

export type ConversationMode = 'single' | 'group'

export interface AgentMember {
  id: string
  name: string
  description?: string
  avatar?: string
  type: string
}

export interface ConversationCreate {
  title: string
  mode: ConversationMode
  agent_ids: string[]
}

export interface ConversationUpdate {
  title?: string
  is_pinned?: boolean
  is_archived?: boolean
}

export interface ConversationListItem {
  id: string
  title?: string
  mode: ConversationMode
  is_pinned: boolean
  is_archived: boolean
  last_message_preview?: string
  last_message_at?: string
  message_count: number
  unread_count: number
  agents: AgentMember[]
  created_at: string
  updated_at: string
}

export interface ConversationResponse extends ConversationListItem {
  user_id: string
  agents: AgentMember[]
}
