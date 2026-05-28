import { computed } from 'vue'
import { chatApi } from '@/api/chat'
import { useChatStore } from '@/stores/chat'
import { useConversationsStore } from '@/stores/conversations'
import { useSSE } from './useSSE'
import type { SelectedRange } from '@/types/api'

export function useChat() {
  const chatStore = useChatStore()
  const conversationsStore = useConversationsStore()
  const sse = useSSE()

  const convId = computed(() => conversationsStore.currentId)
  const isStreaming = computed(() => !!convId.value && chatStore.isStreamingFor(convId.value))

  async function sendMessage(
    content: string,
    mentions: string[] = [],
    selectedRange?: SelectedRange,
  ) {
    const id = conversationsStore.currentId
    if (!id) return

    chatStore.addUserMessage(id, content)

    const response = await chatApi.send({
      conversation_id: id,
      content,
      mention_ids: mentions.length ? mentions : undefined,
      selected_range: selectedRange,
    })

    sse.connect(id)

    return response
  }

  async function stopGeneration() {
    const id = conversationsStore.currentId
    if (!id) return

    try {
      await chatApi.stop({ conversation_id: id })
    } catch {
      sse.disconnect(id)
      chatStore.finishStreaming(id)
    }
  }

  return { sendMessage, stopGeneration, isStreaming, convId }
}