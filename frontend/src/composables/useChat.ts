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