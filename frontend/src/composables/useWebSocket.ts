import { ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useConversationsStore } from '@/stores/conversations'

// per-conversation WS connections (module-level singleton)
const sockets = ref<Map<string, WebSocket>>(new Map())

function getWsBase(): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/api/v1`
}

function connect(conversationId: string, userId = 'default') {
  if (sockets.value.has(conversationId)) return
  const url = `${getWsBase()}/ws/${conversationId}?user_id=${userId}`
  const ws = new WebSocket(url)

  ws.onopen = () => console.log(`[WS] connected conversation=${conversationId}`)

  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data)
      if (message.type === 'approval_acknowledged') {
        const chatStore = useChatStore()
        const convId = useConversationsStore().currentId ?? conversationId
        chatStore.resolveApproval(
          convId,
          message.message_id,
          message.block_id,
          message.decision === 'approve' ? 'approved' : 'rejected',
        )
      }
    } catch (e) {
      console.error('[WS] error handling message', e)
    }
  }

  ws.onclose = () => {
    console.log(`[WS] disconnected conversation=${conversationId}`)
    sockets.value.delete(conversationId)
  }

  ws.onerror = (e) => console.error(`[WS] error conversation=${conversationId}`, e)
  sockets.value.set(conversationId, ws)
}

function disconnect(conversationId?: string) {
  if (conversationId) {
    sockets.value.get(conversationId)?.close()
    sockets.value.delete(conversationId)
  } else {
    for (const ws of sockets.value.values()) ws.close()
    sockets.value.clear()
  }
}

function sendApprovalDecision(
  conversationId: string,
  payload: { messageId: string; blockId: string; decision: 'approve' | 'reject'; reason?: string },
) {
  const ws = sockets.value.get(conversationId)
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    console.warn('[WS] not connected, cannot send approval_decision')
    return false
  }
  ws.send(JSON.stringify({
    type: 'approval_decision',
    message_id: payload.messageId,
    block_id: payload.blockId,
    decision: payload.decision,
    reason: payload.reason ?? null,
  }))
  return true
}

export function useWebSocket() {
  return { connect, disconnect, sendApprovalDecision, sockets }
}
