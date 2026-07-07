export type AgentType = 'claude' | 'codex' | 'opencode' | 'custom' | 'anthropic_sdk'

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
  skillIds: string[]
  mcpServerIds: string[]
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
  mcpServerIds: string[]
}
