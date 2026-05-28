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

  const isStreaming = computed(() => chatStore.isStreaming)
  const currentConvId = computed(() => conversationsStore.currentId)

  async function sendMessage(
    content: string,
    mentions: string[] = [],
    selectedRange?: SelectedRange,
  ) {
    const convId = conversationsStore.currentId
    if (!convId) return

    chatStore.addUserMessage(convId, content)

    const response = await chatApi.send({
      conversation_id: convId,
      content,
      mention_ids: mentions.length ? mentions : undefined,
      selected_range: selectedRange,
    })

    if (!chatStore.isStreaming) {
      sse.connect(convId)
    }

    return response
  }

  async function stopGeneration() {
    const convId = conversationsStore.currentId
    if (!convId) return

    try {
      await chatApi.stop({ conversation_id: convId })
    } catch {
      // API 调用失败时强制清理作为兜底
      sse.disconnect()
      chatStore.finishStreaming(convId)
    }
    // 正常流程：后端会依次发送 agent_error → round_done → queue_drained
    // 由 useSSE 的 handleEvent 自然处理，无需手动 disconnect/finishStreaming
  }

  return { sendMessage, stopGeneration, isStreaming, currentConvId }
}
