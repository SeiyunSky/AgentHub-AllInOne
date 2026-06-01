import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ContentBlock, MessageResponse } from '@/types/api'
import type { AgentMessage, Message, UIBlock, UIApprovalBlock, ReplyPreview } from '@/types/chat'

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
  // Per-conversation message storage
  const messageMap = ref<Map<string, Message[]>>(new Map())

  // Per-conversation streaming state
  const streamingMap = ref<Map<string, (AgentMessage & { blocks?: StreamingBlock[] })>>(new Map())
  const streamingConvIds = ref<Set<string>>(new Set())

  // Per-conversation pending approvals
  const pendingApprovals = ref<Map<string, { messageId: string; blockId: string; action: string; detail: string }>>(new Map())

  // Per-conversation input state
  const inputDrafts = ref<Map<string, string>>(new Map())
  const inputHtmlDrafts = ref<Map<string, string>>(new Map())
  const replyPreviews = ref<Map<string, ReplyPreview>>(new Map())

  // ── Getters ──

  function getMessages(convId: string): Message[] {
    return messageMap.value.get(convId) ?? []
  }

  function setMessages(convId: string, msgs: Message[]) {
    messageMap.value.set(convId, msgs)
  }

  function isStreamingFor(convId: string): boolean {
    return streamingConvIds.value.has(convId)
  }

  function getStreamingMessage(convId: string): (AgentMessage & { blocks?: StreamingBlock[] }) | null {
    return streamingMap.value.get(convId) ?? null
  }

  function getPendingApproval(convId: string): { messageId: string; blockId: string; action: string; detail: string } | null {
    return pendingApprovals.value.get(convId) ?? null
  }

  function getInputDraft(convId: string): string {
    return inputDrafts.value.get(convId) ?? ''
  }

  function setInputDraft(convId: string, text: string, html?: string) {
    if (text) {
      inputDrafts.value.set(convId, text)
      if (html) inputHtmlDrafts.value.set(convId, html)
    } else {
      inputDrafts.value.delete(convId)
      inputHtmlDrafts.value.delete(convId)
    }
  }

  function getInputHtmlDraft(convId: string): string {
    return inputHtmlDrafts.value.get(convId) ?? ''
  }

  function getReplyPreview(convId: string): ReplyPreview | null {
    return replyPreviews.value.get(convId) ?? null
  }

  function setReplyPreview(convId: string, preview: ReplyPreview | null) {
    if (preview) {
      replyPreviews.value.set(convId, preview)
    } else {
      replyPreviews.value.delete(convId)
    }
  }

  function currentMessages(convId: string): Message[] {
    const base = getMessages(convId)
    const streaming = getStreamingMessage(convId)
    if (streaming && isStreamingFor(convId)) {
      return [...base, streaming]
    }
    return base
  }

  // Global streaming state for UI checks (any conversation streaming)
  const isAnyStreaming = computed(() => streamingConvIds.value.size > 0)

  // ── Actions ──

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
    streamingConvIds.value.add(convId)
    streamingMap.value.set(convId, {
      id: messageId,
      type: 'agent',
      agentId,
      agentName,
      content: '',
      timestamp: new Date(),
      blocks: [],
    })
  }

  function appendBlock(convId: string, block: ContentBlock) {
    const streaming = streamingMap.value.get(convId)
    if (!streaming) return
    const uiBlock = apiBlockToUI(block)
    streaming.blocks = [...(streaming.blocks ?? []), uiBlock]

    if (block.type === 'approval' && block.status === 'pending') {
      pendingApprovals.value.set(convId, {
        messageId: streaming.id,
        blockId: block.block_id,
        action: block.action,
        detail: block.detail,
      })
    }
  }

  function updateBlock(convId: string, blockId: string, delta: Record<string, unknown>) {
    const streaming = streamingMap.value.get(convId)
    if (!streaming?.blocks) return
    const idx = streaming.blocks.findIndex(b => {
      const anyB = b as Record<string, unknown>
      return anyB.block_id === blockId
    })
    if (idx === -1) return
    const block = streaming.blocks[idx] as Record<string, unknown>
    for (const [key, value] of Object.entries(delta)) {
      if (typeof value === 'string' && typeof block[key] === 'string') {
        block[key] = (block[key] as string) + value
      } else {
        block[key] = value
      }
    }
    streaming.blocks = [...streaming.blocks]
  }

  function finishBlock(convId: string, blockId: string, finalFields?: Record<string, unknown>) {
    const streaming = streamingMap.value.get(convId)
    if (!streaming?.blocks || !finalFields) return
    const block = streaming.blocks.find(b => {
      const anyB = b as Record<string, unknown>
      return anyB.block_id === blockId
    })
    if (!block) return
    const anyBlock = block as Record<string, unknown>
    for (const [key, value] of Object.entries(finalFields)) {
      anyBlock[key] = value
    }
    streaming.blocks = [...streaming.blocks]
  }

  function commitStreamingMessage(convId: string) {
    const streaming = streamingMap.value.get(convId)
    if (!streaming) return
    const msgs = [...getMessages(convId)]
    msgs.push(streaming)
    setMessages(convId, msgs)
    streamingMap.value.delete(convId)
  }

  function finishStreaming(convId: string) {
    commitStreamingMessage(convId)
    streamingConvIds.value.delete(convId)
    pendingApprovals.value.delete(convId)
  }

  function clearRound(convId: string) {
    commitStreamingMessage(convId)
    streamingConvIds.value.delete(convId)
    // pendingApprovals is only cleared by resolveApproval (user decision) or finishStreaming (agent_error/cancel)
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
    const streaming = streamingMap.value.get(convId)
    if (streaming?.blocks) {
      const block = streaming.blocks.find(b => {
        const anyB = b as Record<string, unknown>
        return anyB.block_id === blockId && (anyB as UIApprovalBlock).type === 'approval'
      }) as UIApprovalBlock | undefined
      if (block) {
        block.status = decision
        block.decidedAt = new Date().toISOString()
        if (reason) block.rejectReason = reason
        streaming.blocks = [...streaming.blocks]
      }
    }

    pendingApprovals.value.delete(convId)
  }

  function updateReaction(convId: string, messageId: string, reaction: 'like' | 'dislike' | undefined) {
    const msgs = getMessages(convId)
    const msg = msgs.find(m => m.id === messageId)
    if (msg) {
      msg.reaction = reaction
      setMessages(convId, [...msgs])
    }
  }

  return {
    // State
    messageMap,
    streamingMap,
    streamingConvIds,
    pendingApprovals,

    // Getters
    getMessages,
    setMessages,
    isStreamingFor,
    getStreamingMessage,
    getPendingApproval,
    getInputDraft,
    setInputDraft,
    getInputHtmlDraft,
    getReplyPreview,
    setReplyPreview,
    currentMessages,
    isAnyStreaming,

    // Actions
    loadFromAPI,
    addUserMessage,
    startStreaming,
    appendBlock,
    updateBlock,
    finishBlock,
    commitStreamingMessage,
    finishStreaming,
    clearRound,
    resolveApproval,
    updateReaction,
  }
})