import { ref } from 'vue'
import { chatApi } from '@/api/chat'
import { useChatStore } from '@/stores/chat'
import { useWorkflowStore } from '@/stores/workflow'
import type { SSEEvent } from '@/types/api'

const controllers = ref<Map<string, AbortController>>(new Map())

function handleEvent(convId: string, event: SSEEvent) {
  console.log('[SSE]', convId, event)
  const chatStore = useChatStore()
  const workflowStore = useWorkflowStore()

  switch (event.type) {
    case 'agent_start':
      chatStore.startStreaming(convId, event.agent_id, event.agent_name, event.message_id)
      workflowStore.onAgentStart(convId, {
        agentId: event.agent_id,
        agentName: event.agent_name,
        threadId: event.thread_id,
        messageId: event.message_id,
      })
      break

    case 'block_start':
      chatStore.appendBlock(convId, event.block, event.agent_id)
      workflowStore.onBlockStart(convId, event.thread_id, {
        blockId: event.block.block_id,
        type: event.block.type,
        toolName: event.block.type === 'tool_use' ? event.block.tool_name : undefined,
      })
      break

    case 'block_delta':
      chatStore.updateBlock(convId, event.block_id, event.delta, event.agent_id)
      break

    case 'block_stop':
      chatStore.finishBlock(convId, event.block_id, event.final_fields, event.agent_id)
      workflowStore.onBlockStop(convId, event.thread_id, event.block_id)
      break

    case 'agent_done':
      chatStore.commitStreamingMessage(convId, event.agent_id)
      workflowStore.onAgentDone(convId, event.thread_id, {
        input: event.tokens_input,
        output: event.tokens_output,
      })
      break

    case 'agent_error':
      chatStore.failStreamingAgent(convId, event.agent_id, event.error)
      workflowStore.onAgentError(convId, event.thread_id, event.error)
      break

    case 'round_done':
      chatStore.clearRound(convId)
      // Keep workflow threads visible after round ends (don't clear)
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
      // Skip if we already disconnected intentionally (queue_drained → disconnect removed the controller)
      if (!controllers.value.has(conversationId)) return
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