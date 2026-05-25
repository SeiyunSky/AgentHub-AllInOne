import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Agent, AgentDraft, AgentCapabilities } from '@/types/agent'

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

export const useAgentsStore = defineStore('agents', () => {
  const agents = ref<Agent[]>([])
  const currentDraft = ref<AgentDraft>({ ...defaultDraft })
  const isLoading = ref(false)
  const isSaving = ref(false)

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
    resetDraft,
    setDraft,
    loadFromAgent,
  }
})