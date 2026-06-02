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

  let loadPromise: Promise<void> | null = null

  async function loadList() {
    if (loadPromise) return loadPromise
    loadPromise = (async () => {
      isLoading.value = true
      try {
        conversations.value = await conversationsApi.list()
      } finally {
        isLoading.value = false
        loadPromise = null
      }
    })()
    return loadPromise
  }

  async function create(title: string, mode: 'single' | 'group', agentIds: string[]) {
    const result = await conversationsApi.create({ title, mode, agent_ids: agentIds })
    conversations.value.unshift(result)
    return result
  }

  async function select(id: string) {
    const prevId = currentId.value
    try {
      const conversation = await conversationsApi.get(id)
      const messages = await conversationsApi.messages(id)
      currentId.value = id
      currentConversation.value = conversation
      const chatStore = useChatStore()
      chatStore.loadFromAPI(id, messages)
    } catch (e) {
      currentId.value = prevId
      throw e
    }
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

  async function remove(id: string) {
    await conversationsApi.delete(id)
    const idx = conversations.value.findIndex(c => c.id === id)
    if (idx !== -1) conversations.value.splice(idx, 1)
    if (currentId.value === id) {
      currentId.value = null
      currentConversation.value = null
    }
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
    remove,
  }
})
