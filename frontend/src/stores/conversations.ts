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

  async function loadList(params?: { limit?: number; offset?: number; include_archived?: boolean }) {
    if (loadPromise) return loadPromise
    loadPromise = (async () => {
      isLoading.value = true
      try {
        const result = await conversationsApi.list(params)
        if (params?.offset && params.offset > 0) {
          conversations.value.push(...result)
        } else {
          conversations.value = result
        }
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

  function updatePreview(id: string, preview: string, at?: string) {
    const idx = conversations.value.findIndex(c => c.id === id)
    if (idx === -1) return
    const now = at ?? new Date().toISOString()
    conversations.value[idx] = {
      ...conversations.value[idx],
      last_message_preview: preview,
      last_message_at: now,
    }
    // 置顶到 unpinned 列表最前（非 pinned 时按时间排序）
    if (!conversations.value[idx].is_pinned) {
      const [item] = conversations.value.splice(idx, 1)
      const firstUnpinned = conversations.value.findIndex(c => !c.is_pinned)
      conversations.value.splice(firstUnpinned === -1 ? 0 : firstUnpinned, 0, item)
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
    updatePreview,
  }
})
