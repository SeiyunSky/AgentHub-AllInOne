import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Agent, AgentDraft, AgentCapabilities } from '@/types/agent'
import { agentsApi, type AgentResponse } from '@/api/agents'

const defaultCapabilities: AgentCapabilities = {
  supportsCode: true,
  supportsDiff: false,
  supportsApproval: false,
  supportsImage: false,
}

const defaultDraft: AgentDraft = {
  name: '',
  description: '',
  type: 'claude',
  systemPrompt: '',
  capabilities: { ...defaultCapabilities },
  tags: [],
  isPublic: false,
}

function mapAgentResponse(a: AgentResponse): Agent {
  return {
    id: a.id,
    name: a.name,
    description: a.description,
    type: a.type as Agent['type'],
    avatar: a.avatar,
    systemPrompt: a.system_prompt,
    capabilities: {
      supportsCode: a.capabilities.supports_code,
      supportsDiff: a.capabilities.supports_diff,
      supportsApproval: a.capabilities.supports_approval,
      supportsImage: a.capabilities.supports_image,
    },
    tags: a.tags,
    isPublic: a.is_public,
    isActive: a.is_active,
    createdAt: new Date(a.created_at),
    updatedAt: new Date(a.updated_at),
  }
}

export const useAgentsStore = defineStore('agents', () => {
  const agents = ref<Agent[]>([])
  const currentDraft = ref<AgentDraft>({ ...defaultDraft })
  const isLoading = ref(false)
  const isSaving = ref(false)

  let loadPromise: Promise<void> | null = null

  async function loadAgents() {
    if (loadPromise) return loadPromise
    loadPromise = (async () => {
      isLoading.value = true
      try {
        const data = await agentsApi.list()
        agents.value = data.map(mapAgentResponse)
      } finally {
        isLoading.value = false
        loadPromise = null
      }
    })()
    return loadPromise
  }

  function resetDraft() {
    currentDraft.value = { ...defaultDraft }
  }

  function setDraft(draft: AgentDraft) {
    currentDraft.value = { ...draft }
  }

  function loadFromAgent(agent: Agent) {
    currentDraft.value = {
      name: agent.name,
      description: agent.description,
      type: agent.type,
      avatar: agent.avatar,
      systemPrompt: agent.systemPrompt,
      capabilities: { ...agent.capabilities },
      tags: [...agent.tags],
      isPublic: agent.isPublic,
    }
  }

  return {
    agents,
    currentDraft,
    isLoading,
    isSaving,
    loadAgents,
    resetDraft,
    setDraft,
    loadFromAgent,
  }
})