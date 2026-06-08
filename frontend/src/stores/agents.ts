import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Agent, AgentDraft } from '@/types/agent'
import { agentsApi, type AgentResponse } from '@/api/agents'

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
    skillIds: a.skill_ids ?? [],
    mcpServerIds: a.mcp_server_ids ?? [],
    createdAt: new Date(a.created_at),
    updatedAt: new Date(a.updated_at),
  }
}

export const useAgentsStore = defineStore('agents', () => {
  const agents = ref<Agent[]>([])
  const isLoading = ref(false)
  const isSaving = ref(false)

  // Draft state — used by AI Builder to pass initial values to create form
  const initialDraft = ref<Partial<AgentDraft> | undefined>(undefined)

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

  function upsertAgent(raw: AgentResponse) {
    const agent = mapAgentResponse(raw)
    const idx = agents.value.findIndex(a => a.id === agent.id)
    if (idx >= 0) {
      agents.value.splice(idx, 1, agent)
    } else {
      agents.value.unshift(agent)
    }
  }

  function removeAgent(id: string) {
    const idx = agents.value.findIndex(a => a.id === id)
    if (idx >= 0) agents.value.splice(idx, 1)
  }

  return {
    agents,
    isLoading,
    isSaving,
    initialDraft,
    loadAgents,
    upsertAgent,
    removeAgent,
  }
})
