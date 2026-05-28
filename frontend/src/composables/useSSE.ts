import { ref } from 'vue'
import { chatApi } from '@/api/chat'
import { useChatStore } from '@/stores/chat'
import type { SSEEvent } from '@/types/api'

const controllers = ref<Map<string, AbortController>>(new Map())

function handleEvent(convId: string, event: SSEEvent) {
  const chatStore = useChatStore()
  switch (event.type) {
    case 'agent_start':
      chatStore.startStreaming(convId, event.agent_id, event.agent_name, event.message_id)
      break

    case 'block_start':
      chatStore.appendBlock(convId, event.block)
      break

    case 'block_delta':
      chatStore.updateBlock(convId, event.block_id, event.delta)
      break

    case 'block_stop':
      chatStore.finishBlock(convId, event.block_id, event.final_fields)
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
      disconnect(convId)
      break
  }
}

function connect(conversationId: string) {
  if (controllers.value.has(conversationId)) return

  controllers.value.set(conversationId, chatApi.stream(conversationId, {
    onEvent: (event: SSEEvent) => handleEvent(conversationId, event),
    onError: (error) => {
      console.error(`SSE error (${conversationId}):`, error)
      const chatStore = useChatStore()
      chatStore.finishStreaming(conversationId)
      controllers.value.delete(conversationId)
    },
    onClose: () => {
      const chatStore = useChatStore()
      chatStore.finishStreaming(conversationId)
      controllers.value.delete(conversationId)
    },
  }))
}

function disconnect(convId?: string) {
  if (convId) {
    controllers.value.get(convId)?.abort()
    controllers.value.delete(convId)
  } else {
    for (const ctrl of controllers.value.values()) {
      ctrl.abort()
    }
    controllers.value.clear()
  }
}

export function useSSE() {
  return { connect, disconnect, controllers }
}