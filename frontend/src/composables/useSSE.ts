import { ref } from 'vue'
import { chatApi } from '@/api/chat'
import { useChatStore } from '@/stores/chat'
import type { SSEEvent } from '@/types/api'

export function useSSE() {
  const chatStore = useChatStore()
  const abortController = ref<AbortController | null>(null)

  function connect(conversationId: string) {
    disconnect()
    chatStore.currentConversationId = conversationId

    abortController.value = chatApi.stream(conversationId, {
      onEvent: (event: SSEEvent) => handleEvent(conversationId, event),
      onError: (error) => {
        console.error('SSE error:', error)
        chatStore.finishStreaming(conversationId)
      },
      onClose: () => {
        chatStore.finishStreaming(conversationId)
      },
    })
  }

  function handleEvent(convId: string, event: SSEEvent) {
    switch (event.type) {
      case 'agent_start':
        chatStore.startStreaming(convId, event.agent_id, event.agent_name, event.message_id)
        chatStore.setAgentActive(event.agent_id, event.agent_name)
        break

      case 'block_start':
        chatStore.appendBlock(event.block)
        break

      case 'block_delta':
        chatStore.updateBlock(event.block_id, event.delta)
        break

      case 'block_stop':
        chatStore.finishBlock(event.block_id, event.final_fields)
        break

      case 'agent_done':
        chatStore.commitStreamingMessage(convId)
        break

      case 'agent_error':
        chatStore.finishStreaming(convId)
        break

      case 'round_done':
        chatStore.clearRound(convId)
        break

      case 'queue_drained':
        disconnect()
        break
    }
  }

  function disconnect() {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
  }

  return { connect, disconnect, abortController }
}
