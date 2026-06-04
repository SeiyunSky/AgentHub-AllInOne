import { ref } from 'vue'
import { chatApi } from '@/api/chat'
import { useChatStore } from '@/stores/chat'
import { useConversationsStore } from '@/stores/conversations'
import { useWorkflowStore } from '@/stores/workflow'
import { useSandboxFilesStore } from '@/stores/sandboxFiles'
import { useDeploymentsStore } from '@/stores/deployments'
import type { SSEEvent } from '@/types/api'

const controllers = ref<Map<string, AbortController>>(new Map())

function handleEvent(convId: string, event: SSEEvent) {
  console.log('[SSE]', convId, event)
  const chatStore = useChatStore()
  const workflowStore = useWorkflowStore()

  switch (event.type) {
    case 'agent_start':
      chatStore.startStreaming(convId, event.agent_id, event.agent_name, event.message_id, event.agent_avatar)
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
            errorMessage: status === 'error' ? (out?.error ?? '部署失败') : undefined,
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
      // 关闭连接，让下一轮发消息时重新建立 SSE
      disconnect(convId)
      break

    case 'message_appended':
      chatStore.appendPersistedMessage(convId, event.message)
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