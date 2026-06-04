import { computed } from 'vue'
import { chatApi } from '@/api/chat'
import { useChatStore } from '@/stores/chat'
import { useConversationsStore } from '@/stores/conversations'
import { useWorkflowStore } from '@/stores/workflow'
import { useSSE } from './useSSE'
import type { SelectedRange } from '@/types/api'

export function useChat() {
  const chatStore = useChatStore()
  const conversationsStore = useConversationsStore()
  const workflowStore = useWorkflowStore()
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

    const tempId = chatStore.addUserMessage(id, content)
    conversationsStore.updatePreview(id, content)

    // 关键顺序:必须先连 SSE 再发 POST。
    // 后端 group 路径 await orchestrator_service.start_loop(...) 阻塞 HTTP 响应,
    // 当 POST /chat 返回时,主 Agent 这一轮的事件已经全部 push 完毕。
    // SSE 是 push-only 不回放,先 POST 后 connect 必然漏掉所有事件 → 前端永远等不到回复。
    sse.connect(id)

    const response = await chatApi.send({
      conversation_id: id,
      content,
      mention_ids: mentions.length ? mentions : undefined,
      selected_range: selectedRange,
    })

    // 后端返回真实 user_message_id 后，替换本地临时 ID，使反馈等操作能正常工作
    if (response && 'user_message_id' in response && response.user_message_id) {
      chatStore.confirmUserMessage(id, tempId, response.user_message_id)
    }

    return response
  }

  async function stopGeneration() {
    const id = conversationsStore.currentId
    if (!id) return

    // 乐观 UI:点击瞬间就把 streaming 气泡 / workflow 节点全部停掉,
    // 不等 HTTP 响应。后端 stop 流程 + cancel 数据库 UPDATE 慢则几秒,
    // 等响应再清 UI 用户会感觉卡死。后端推的 round_done 是兜底确认。
    chatStore.finishStreaming(id)
    workflowStore.markActiveAsCancelled(id)

    try {
      await chatApi.stop({ conversation_id: id })
    } catch (e) {
      // 失败时也强制断开 SSE,避免连接挂死
      console.warn('[stop] request failed', e)
    } finally {
      // 不论后端是否成功，断 SSE 防止后续 token 继续到达
      sse.disconnect(id)
    }
  }

  return { sendMessage, stopGeneration, isStreaming, convId }
}