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
    createdAt: new Date(a.created_at),
    updatedAt: new Date(a.updated_at),
  }
}

export const useAgentsStore = defineStore('agents', () => {
  const agents = ref<Agent[]>([])
  const isLoading = ref(false)
  const isSaving = ref(false)

  // Form state — shared between sidebar and main panel
  const showConfigForm = ref(false)
  const editingAgentId = ref<string | undefined>(undefined)
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

  function openCreate() {
    editingAgentId.value = undefined
    initialDraft.value = undefined
    showConfigForm.value = true
  }

  function openEdit(agentId: string) {
    editingAgentId.value = agentId
    initialDraft.value = undefined
    showConfigForm.value = true
  }

  function closeConfigForm() {
    showConfigForm.value = false
    editingAgentId.value = undefined
    initialDraft.value = undefined
  }

  return {
    agents,
    isLoading,
    isSaving,
    showConfigForm,
    editingAgentId,
    initialDraft,
    loadAgents,
    openCreate,
    openEdit,
    closeConfigForm,
  }
})