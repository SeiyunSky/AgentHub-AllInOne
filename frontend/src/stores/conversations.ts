import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ConversationListItem, ConversationResponse } from '@/types/conversation'
import { conversationsApi } from '@/api/conversations'
import { useChatStore } from './chat'

export const useConversationsStore = defineStore('conversations', () => {
  const conversations = ref<ConversationListItem[]>([])
  const currentId = ref<string | null>(null)
  const currentConversation = ref<ConversationResponse | null>(null)
  const isLoading = ref(false)

  async function loadList() {
    isLoading.value = true
    try {
      conversations.value = await conversationsApi.list()
    } finally {
      isLoading.value = false
    }
  }

  async function create(title: string, mode: 'single' | 'group', agentIds: string[]) {
    const result = await conversationsApi.create({ title, mode, agent_ids: agentIds })
    conversations.value.unshift(result)
    return result
  }

  async function select(id: string) {
    currentId.value = id
    currentConversation.value = await conversationsApi.get(id)

    const chatStore = useChatStore()
    const messages = await conversationsApi.messages(id)
    chatStore.loadFromAPI(id, messages)
  }

  async function update(id: string, data: { title?: string; is_pinned?: boolean; is_archived?: boolean }) {
    const result = await conversationsApi.update(id, data)
    const idx = conversations.value.findIndex(c => c.id === id)
    if (idx !== -1) {
      conversations.value[idx] = result
    }
    if (currentId.value === id) {
      currentConversation.value = result
    }
    return result
  }

  return {
    conversations,
    currentId,
    currentConversation,
    isLoading,
    loadList,
    create,
    select,
    update,
  }
})
