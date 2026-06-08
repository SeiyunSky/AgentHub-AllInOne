import { ref } from 'vue'
import { chatApi } from '@/api/chat'
import { useChatStore } from '@/stores/chat'
import { useConversationsStore } from '@/stores/conversations'
import { useWorkflowStore } from '@/stores/workflow'
import { useSandboxFilesStore } from '@/stores/sandboxFiles'
import { useDeploymentsStore } from '@/stores/deployments'
import { i18n } from '@/i18n'
import type { SSEEvent } from '@/types/api'

const controllers = ref<Map<string, AbortController>>(new Map())

/**
 * 判断消息是否已存在于消息列表中且已完成（非 streaming 状态）
 * 用于过滤回放时的重复事件
 */
function isMessageCompleted(convId: string, messageId: string): boolean {
  const chatStore = useChatStore()
  const msgs = chatStore.getMessages(convId)
  // 查找该消息ID是否已存在于历史消息列表中
  const existingMsg = msgs.find(m => m.id === messageId)
  if (!existingMsg) return false

  // 如果存在，检查是否还在 streaming 状态
  // streaming 状态的 agent 不在 messageMap 中，而是在 streamingMap 中
  // 所以如果能在 messageMap 中找到，说明已经完成（agent_done 已触发）
  return existingMsg.type === 'agent'
}

/**
 * 判断是否应该忽略该事件（用于回放场景）
 * 策略：agent_start 是入口事件，如果 message_id 已完成，忽略整个消息链
 */
function shouldIgnoreEvent(convId: string, event: SSEEvent): boolean {
  // agent_start：检查 message_id 是否已完成
  if (event.type === 'agent_start') {
    return isMessageCompleted(convId, event.message_id)
  }

  // 其他事件（block_start/delta/stop, agent_done/error）：如果同 message_id 的 agent_start 被忽略，也忽略这些
  // 但我们没有记录哪些 message_id 被忽略了，所以实时检查
  if ('message_id' in event) {
    return isMessageCompleted(convId, event.message_id as string)
  }

  return false
}

function handleEvent(convId: string, event: SSEEvent) {
  const chatStore = useChatStore()
  const workflowStore = useWorkflowStore()

  // 过滤已完成消息的重复事件
  if (shouldIgnoreEvent(convId, event)) {
    console.log("discard event:", event);
    
    return
  }

  switch (event.type) {
    case 'agent_start':
      chatStore.startStreaming(convId, event.agent_id, event.agent_name, event.message_id, event.agent_avatar)
      workflowStore.onAgentStart(convId, {
        agentId: event.agent_id,
        agentName: event.agent_name,
        agentAvatar: event.agent_avatar,
        threadId: event.thread_id,
        messageId: event.message_id,
        avatar: event.agent_avatar,
      })
      break

    case 'block_start':
      chatStore.appendBlock(convId, event.block, event.agent_id)
      workflowStore.onBlockStart(convId, event.thread_id, {
        blockId: event.block.block_id,
        type: event.block.type,
        toolName: event.block.type === 'tool_use' ? (event.block as any).tool_name : undefined,
        toolInput: event.block.type === 'tool_use' ? (event.block as any).input ?? undefined : undefined,
        content: (event.block.type === 'text' || event.block.type === 'thinking') ? (event.block as any).content : undefined,
        language: event.block.type === 'code' ? (event.block as any).language : undefined,
        code: event.block.type === 'code' ? (event.block as any).code : undefined,
        filename: event.block.type === 'code' ? (event.block as any).filename : undefined,
      })
      // PostExecutionHook 在 create_file/edit_file 成功后会推 CodeBlock,带 filename
      // → 当前会话沙箱有新文件,触发 Files Tab 自动刷新(debounce 防止连续多文件刷太多次)
      if (event.block.type === 'code' && (event.block as any).filename) {
        useSandboxFilesStore().loadFilesDebounced(convId)
      }
      break

    case 'block_delta':
      chatStore.updateBlock(convId, event.block_id, event.delta, event.agent_id)
      workflowStore.onBlockDelta(convId, event.thread_id, event.block_id, event.delta)
      break

    case 'block_stop':
      chatStore.finishBlock(convId, event.block_id, event.final_fields, event.agent_id)
      workflowStore.onBlockStop(convId, event.thread_id, event.block_id,
        typeof event.final_fields?.content === 'string' ? event.final_fields.content : undefined)
      // 捕获 deploy_app 工具调用结果,落到 deployments store
      // (主 Agent 调 deploy_app 工具,后端在 final_fields 里带 tool_name + output JSON)
      if (event.final_fields?.tool_name === 'deploy_app') {
        try {
          const out = typeof event.final_fields.output === 'string'
            ? JSON.parse(event.final_fields.output)
            : event.final_fields.output
          const status = (event.final_fields.status === 'completed' && out?.status === 'running')
            ? 'running' : 'error'
          useDeploymentsStore().addDeployment({
            id: event.block_id,
            conversationId: convId,
            url: out?.url ?? `/preview/${convId}/`,
            entryPoint: out?.entry_point ?? 'app.py',
            status,
            active: status === 'running',
            startedAt: Date.now(),
            logs: out?.logs ?? '',
            errorMessage: status === 'error' ? (out?.error ?? i18n.global.t('deployments.deployFailed')) : undefined,
          })
        } catch (e) {
          console.warn('[SSE] deploy_app result parse failed', e)
        }
      }
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
      // 同步 workflow:把所有还在 running 的 thread 节点标 cancelled
      // (stop 流程下后端不会发 agent_done/agent_error,workflow 节点会永远转圈)
      workflowStore.markActiveAsCancelled(convId)
      // 把当前轮内存中的 workflow 持久化到后端（最新一份会追加到 historyMap 末尾）
      void workflowStore.persistCurrent(convId)
      // sync last agent message to conversation list preview
      {
        const conversationsStore = useConversationsStore()
        const msgs = chatStore.getMessages(convId)
        const last = [...msgs].reverse().find(m => m.type === 'agent')
        if (last) {
          const text = last.blocks?.find(b => b.type === 'text')
          const preview = text ? (text as { content: string }).content : last.content
          conversationsStore.updatePreview(convId, preview.slice(0, 100))
        }
      }
      break

    case 'message_appended':
      chatStore.appendPersistedMessage(convId, event.message)
      break

    case 'read_receipt':
      chatStore.addReadReceipt(event.message_id, event.agent_id, event.agent_name, event.agent_avatar)
      break

    case 'queue_drained':
      disconnect(convId)
      break
  }
}

function connect(conversationId: string, afterMessageId?: string) {
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
    afterMessageId,
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
  return {
    connect,
    disconnect,
    controllers,
  }
}