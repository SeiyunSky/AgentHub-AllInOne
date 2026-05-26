import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ContentBlock, MessageResponse } from '@/types/api'
import type { AgentMessage, Message, UIBlock, UIApprovalBlock } from '@/types/chat'

type StreamingBlock = UIBlock & { block_id?: string }

function apiBlockToUI(block: ContentBlock): StreamingBlock {
  const id = block.block_id
  switch (block.type) {
    case 'text':
      return { block_id: id, type: 'text', content: block.content }
    case 'thinking':
      return { block_id: id, type: 'thinking', content: block.content, duration: block.duration_ms }
    case 'tool_use':
      return {
        block_id: id,
        type: 'tool_use',
        toolName: block.tool_name,
        input: block.input,
        output: block.output,
        status: block.status,
      }
    case 'code':
      return {
        block_id: id,
        type: 'code',
        code: block.code,
        filename: block.filename,
        language: block.language,
        oldCode: block.old_code,
      }
    case 'deployment':
      return {
        block_id: id,
        type: 'deployment',
        title: block.title,
        status: block.status,
        url: block.url,
        logs: block.logs,
        progress: block.progress,
      }
    case 'image':
      return { block_id: id, type: 'image', src: block.src, alt: block.alt, caption: block.caption }
    case 'artifacts':
      return { block_id: id, type: 'artifacts', item: block.items[0] }
    case 'approval':
      return {
        block_id: id,
        type: 'approval',
        action: block.action,
        detail: block.detail,
        status: block.status,
        decidedAt: block.decided_at,
        rejectReason: block.reject_reason,
      }
  }
}

function toUIMessage(msg: MessageResponse): Message {
  if (msg.role === 'user') {
    const textBlock = msg.blocks.find(b => b.type === 'text')
    return {
      id: msg.id,
      type: 'user',
      content: textBlock ? (textBlock as { content: string }).content : '',
      timestamp: new Date(msg.created_at),
      reaction: msg.feedback === 'up' ? 'like' : msg.feedback === 'down' ? 'dislike' : undefined,
    }
  }

  const uiBlocks = msg.blocks.map(apiBlockToUI)
  return {
    id: msg.id,
    type: 'agent',
    agentId: msg.agent_id ?? '',
    agentName: msg.sender ?? msg.agent_id ?? 'Agent',
    content: uiBlocks.find(b => b.type === 'text')?.content ?? '',
    timestamp: new Date(msg.created_at),
    blocks: uiBlocks,
    model: msg.model ?? undefined,
    sender: msg.sender ?? undefined,
    tokensInput: msg.tokens_input ?? undefined,
    tokensOutput: msg.tokens_output ?? undefined,
    latencyMs: msg.latency_ms ?? undefined,
    reaction: msg.feedback === 'up' ? 'like' : msg.feedback === 'down' ? 'dislike' : undefined,
  } as AgentMessage
}

export const useChatStore = defineStore('chat', () => {
  const messageMap = ref<Map<string, Message[]>>(new Map())
  const streamingMessage = ref<(AgentMessage & { blocks?: StreamingBlock[] }) | null>(null)
  const activeAgents = ref<{ id: string; name: string; role: string; status: 'active' | 'processing' | 'idle' | 'error' }[]>([])
  const isStreaming = ref(false)
  const currentConversationId = ref<string | null>(null)
  const pendingApproval = ref<{ messageId: string; blockId: string; action: string; detail: string } | null>(null)

  function getMessages(convId: string): Message[] {
    return messageMap.value.get(convId) ?? []
  }

  function setMessages(convId: string, msgs: Message[]) {
    messageMap.value.set(convId, msgs)
  }

  function currentMessages(convId: string): Message[] {
    const base = getMessages(convId)
    if (streamingMessage.value && currentConversationId.value === convId) {
      return [...base, streamingMessage.value]
    }
    return base
  }

  function loadFromAPI(convId: string, apiMessages: MessageResponse[]) {
    setMessages(convId, apiMessages.map(toUIMessage))
  }

  function addUserMessage(convId: string, content: string) {
    const msgs = [...getMessages(convId)]
    msgs.push({
      id: `local-${Date.now()}`,
      type: 'user',
      content,
      timestamp: new Date(),
    })
    setMessages(convId, msgs)
  }

  function startStreaming(convId: string, agentId: string, agentName: string, messageId: string) {
    isStreaming.value = true
    currentConversationId.value = convId
    streamingMessage.value = {
      id: messageId,
      type: 'agent',
      agentId,
      agentName,
      content: '',
      timestamp: new Date(),
      blocks: [],
    }
  }

  function appendBlock(block: ContentBlock) {
    if (!streamingMessage.value) return
    const uiBlock = apiBlockToUI(block)
    streamingMessage.value.blocks = [...(streamingMessage.value.blocks ?? []), uiBlock]

    if (block.type === 'approval' && block.status === 'pending') {
      pendingApproval.value = {
        messageId: streamingMessage.value.id,
        blockId: block.block_id,
        action: block.action,
        detail: block.detail,
      }
    }
  }

  function updateBlock(blockId: string, delta: Record<string, unknown>) {
    if (!streamingMessage.value?.blocks) return
    const idx = streamingMessage.value.blocks.findIndex(b => {
      const anyB = b as Record<string, unknown>
      return anyB.block_id === blockId
    })
    if (idx === -1) return
    const block = streamingMessage.value.blocks[idx] as Record<string, unknown>
    for (const [key, value] of Object.entries(delta)) {
      if (typeof value === 'string' && typeof block[key] === 'string') {
        block[key] = (block[key] as string) + value
      } else {
        block[key] = value
      }
    }
    streamingMessage.value.blocks = [...streamingMessage.value.blocks]
  }

  function finishBlock(blockId: string, finalFields?: Record<string, unknown>) {
    if (!streamingMessage.value?.blocks || !finalFields) return
    const block = streamingMessage.value.blocks.find(b => {
      const anyB = b as Record<string, unknown>
      return anyB.block_id === blockId
    })
    if (!block) return
    const anyBlock = block as Record<string, unknown>
    for (const [key, value] of Object.entries(finalFields)) {
      anyBlock[key] = value
    }
    streamingMessage.value.blocks = [...streamingMessage.value.blocks]
  }

  function commitStreamingMessage(convId: string) {
    if (!streamingMessage.value) return
    const msgs = [...getMessages(convId)]
    msgs.push(streamingMessage.value)
    setMessages(convId, msgs)
    streamingMessage.value = null
  }

  function finishStreaming(convId: string) {
    commitStreamingMessage(convId)
    isStreaming.value = false
    activeAgents.value = []
  }

  function setAgentActive(agentId: string, name: string) {
    const existing = activeAgents.value.find(a => a.id === agentId)
    if (existing) {
      existing.status = 'processing'
    } else {
      activeAgents.value.push({ id: agentId, name, role: 'Agent', status: 'processing' })
    }
  }

  function clearRound(convId: string) {
    commitStreamingMessage(convId)
    isStreaming.value = false
    activeAgents.value = []
    currentConversationId.value = null
  }

  function resolveApproval(convId: string, messageId: string, blockId: string, decision: 'approved' | 'rejected', reason?: string) {
    // Update the block in messages
    const msgs = getMessages(convId)
    const msg = msgs.find(m => m.id === messageId)
    if (msg && msg.type === 'agent' && msg.blocks) {
      const block = msg.blocks.find(b => {
        const anyB = b as Record<string, unknown>
        return anyB.block_id === blockId && (anyB as UIApprovalBlock).type === 'approval'
      }) as UIApprovalBlock | undefined
      if (block) {
        block.status = decision
        block.decidedAt = new Date().toISOString()
        if (reason) block.rejectReason = reason
      }
      setMessages(convId, [...msgs])
    }

    // Also check streaming message
    if (streamingMessage.value?.blocks) {
      const block = streamingMessage.value.blocks.find(b => {
        const anyB = b as Record<string, unknown>
        return anyB.block_id === blockId && (anyB as UIApprovalBlock).type === 'approval'
      }) as UIApprovalBlock | undefined
      if (block) {
        block.status = decision
        block.decidedAt = new Date().toISOString()
        if (reason) block.rejectReason = reason
        streamingMessage.value.blocks = [...streamingMessage.value.blocks]
      }
    }

    pendingApproval.value = null
  }

  return {
    messageMap,
    streamingMessage,
    activeAgents,
    isStreaming,
    currentConversationId,
    getMessages,
    setMessages,
    currentMessages,
    loadFromAPI,
    addUserMessage,
    startStreaming,
    appendBlock,
    updateBlock,
    finishBlock,
    commitStreamingMessage,
    finishStreaming,
    setAgentActive,
    clearRound,
    pendingApproval,
    resolveApproval,
  }
})
