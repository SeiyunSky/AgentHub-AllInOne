export type AgentType = 'claude' | 'codex' | 'opencode' | 'custom'

export interface AgentCapabilities {
  supportsCode: boolean
  supportsDiff: boolean
  supportsApproval: boolean
  supportsImage: boolean
}

export interface Agent {
  id: string
  name: string
  description?: string
  type: AgentType
  avatar?: string
  systemPrompt?: string
  capabilities: AgentCapabilities
  tags: string[]
  isPublic: boolean
  isActive: boolean
  createdAt: Date
  updatedAt: Date
}

export interface AgentDraft {
  name: string
  description?: string
  type: AgentType
  avatar?: string
  systemPrompt?: string
  capabilities: AgentCapabilities
  tags: string[]
  isPublic: boolean
  isActive: boolean
  skillIds: string[]
}
