import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ContentBlock, MessageResponse } from '@/types/api'
import type { AgentMessage, Message, UIBlock, UIApprovalBlock, ReplyPreview } from '@/types/chat'
import { useConversationsStore } from '@/stores/conversations'

type StreamingBlock = UIBlock & { block_id?: string }

/**
 * 单个 Agent 的并发流式状态。
 * 群聊场景下同一 conversation 会有多个 Agent 同时 streaming(主 Agent + 各子 Agent),
 * 每个 Agent 一份独立的 AgentStreamingState,按 agentId 索引。
 */
export type AgentActivity =
  | 'thinking'      // 还没产生 block,LLM 正在思考
  | 'typing'        // text block 正在 delta 流入
  | 'tool'          // 调工具中(tool_use block running)
  | 'idle'          // 暂时没事件了(可能在等子 Thread)

export interface AgentStreamingState {
  messageId: string
  agentId: string
  agentName: string
  avatar?: string
  blocks: StreamingBlock[]
  activity: AgentActivity
  currentTool?: string         // 例:"dispatch_to_agent" / "read_thread_result"
  startedAt: Date
  lastEventAt: Date
}

/**
 * 主 Agent 派出去的子 Thread 调度状态。
 * 来源:主 Agent 调 dispatch_to_agent / create_task_plan / add_task 工具时,
 *      前端从 tool_use block 的 input 里抠出 task 列表,本地虚拟出来。
 *      然后再根据 SSE 事件 (agent_start/agent_done/agent_error) 推进状态。
 */
export type ThreadStatus = 'pending' | 'running' | 'done' | 'error'

export interface ThreadActivity {
  threadId: string
  agentId: string
  agentName: string
  status: ThreadStatus
  blockedBy: string[]
  currentTool?: string
  bytesProduced: number
  startedAt?: Date
  finishedAt?: Date
  errorMessage?: string
}

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
    case 'meme':
      return { block_id: id, type: 'meme', memeId: block.meme_id, url: block.url, description: block.description }
    case 'approval':
      return {
        block_id: id,
        type: 'approval',
        blockId: id,
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
    avatar: msg.agent_avatar ?? undefined,
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

/** 把 streaming 状态映射成给 MessageList 显示用的 AgentMessage */
function streamingToMessage(s: AgentStreamingState): AgentMessage {
  return {
    id: s.messageId,
    type: 'agent',
    agentId: s.agentId,
    agentName: s.agentName,
    avatar: s.avatar,
    content: (s.blocks.find(b => b.type === 'text') as { content: string } | undefined)?.content ?? '',
    timestamp: s.startedAt,
    blocks: s.blocks,
  }
}

export const useChatStore = defineStore('chat', () => {
  // 已落库历史消息(每个会话一份,从 /messages 接口加载)
  const messageMap = ref<Map<string, Message[]>>(new Map())

  // 多 Agent 并行流式状态:每个会话内,每个 agent_id 一条独立的 streaming 气泡
  // 旧版 streamingMap<convId, ONE message> 只能存 1 个,群聊会互相覆盖;新版按 agentId 索引,
  // 主 Agent + 多个子 Agent 可同时显示
  const streamingMap = ref<Map<string, Map<string, AgentStreamingState>>>(new Map())
  const streamingConvIds = ref<Set<string>>(new Set())

  // 主 Agent 派出去的 Thread 调度卡片(同一会话多个 task 并行 / 依赖等)
  const threadActivitiesMap = ref<Map<string, Map<string, ThreadActivity>>>(new Map())

  // 等待用户决策的审批
  const pendingApprovals = ref<Map<string, { messageId: string; blockId: string; action: string; detail: string }>>(new Map())

  // broadcast 模式已读回执：message_id → [{ agentId, agentName, agentAvatar }]
  const readReceiptsMap = ref<Map<string, { agentId: string; agentName: string; agentAvatar?: string }[]>>(new Map())

  // broadcast 模式本轮新收到的消息 ID 集合（用于打字流动画，播放完后清除）
  const newBroadcastMessageIds = ref<Set<string>>(new Set())

  // 输入草稿、回复引用
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

  /** 获取某会话最后一条消息的ID(用于刷新回放) */
  function getLastMessageId(convId: string): string | undefined {
    const msgs = getMessages(convId)
    if (msgs.length === 0) return undefined
    // 返回最后一条消息的ID
    return msgs[msgs.length - 1].id
  }

  function isStreamingFor(convId: string): boolean {
    return streamingConvIds.value.has(convId)
  }

  /** 拿某会话所有正在 streaming 的 Agent(数组,按 startedAt 排序) */
  function getStreamingAgents(convId: string): AgentStreamingState[] {
    const inner = streamingMap.value.get(convId)
    if (!inner) return []
    return [...inner.values()].sort((a, b) => a.startedAt.getTime() - b.startedAt.getTime())
  }

  /** 拿某会话某 Agent 的 streaming 状态 */
  function getAgentStreaming(convId: string, agentId: string): AgentStreamingState | null {
    return streamingMap.value.get(convId)?.get(agentId) ?? null
  }

  /** 兼容老接口:返回最近一条 streaming(给老组件用,新组件改用 getStreamingAgents) */
  function getStreamingMessage(convId: string): AgentStreamingState | null {
    const list = getStreamingAgents(convId)
    return list.length > 0 ? list[list.length - 1] : null
  }

  /** 拿某会话所有 Thread 调度卡片(按 startedAt / pending 在前) */
  function getThreadActivities(convId: string): ThreadActivity[] {
    const inner = threadActivitiesMap.value.get(convId)
    if (!inner) return []
    return [...inner.values()].sort((a, b) => {
      const aTime = a.startedAt?.getTime() ?? 0
      const bTime = b.startedAt?.getTime() ?? 0
      return aTime - bTime
    })
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

  /**
   * MessageList 渲染用:已落库消息 + 所有正在 streaming 的 Agent 气泡(按时序追加)
   * 多个 Agent 同时 streaming → 多个气泡同时显示(Teams 风格)
   */
  function currentMessages(convId: string): Message[] {
    const base = getMessages(convId)
    const streamings = getStreamingAgents(convId)
    if (streamings.length === 0) return base
    return [...base, ...streamings.map(streamingToMessage)]
  }

  const isAnyStreaming = computed(() => streamingConvIds.value.size > 0)

  // ── Actions ──

  function loadFromAPI(convId: string, apiMessages: MessageResponse[]) {
    setMessages(convId, apiMessages.map(toUIMessage))
  }

  /** 在现有消息前插入历史消息（用于加载更多） */
  function prependMessages(convId: string, olderMessages: MessageResponse[]) {
    const existing = getMessages(convId)
    const older = olderMessages.map(toUIMessage)
    setMessages(convId, [...older, ...existing])
  }

  function addUserMessage(convId: string, content: string): string {
    const tempId = `local-${Date.now()}`
    const msgs = [...getMessages(convId)]
    msgs.push({
      id: tempId,
      type: 'user',
      content,
      timestamp: new Date(),
    })
    setMessages(convId, msgs)
    return tempId
  }

  /** 后端返回真实 message_id 后，用它替换本地临时 ID */
  function confirmUserMessage(convId: string, tempId: string, realId: string) {
    const msgs = getMessages(convId)
    const msg = msgs.find(m => m.id === tempId)
    if (msg) {
      msg.id = realId
      setMessages(convId, [...msgs])
    }
  }

  /** SSE message_appended：把已落库的完整消息直接 append 进列表，不走 streaming */
  function appendPersistedMessage(convId: string, msg: MessageResponse) {
    const msgs = getMessages(convId)
    const ui = toUIMessage(msg)
    const existingIdx = msgs.findIndex(m => m.id === msg.id)
    if (existingIdx !== -1 && msgs[existingIdx].type !== 'user') {
      // 已有同 id 的非用户消息（如 streaming commit 版）→ 替换为落库版本
      const updated = [...msgs]
      updated[existingIdx] = ui
      setMessages(convId, updated)
    } else if (existingIdx === -1) {
      // 找不到 → append
      setMessages(convId, [...msgs, ui])
    }
    // existingIdx 找到的是 user 消息 → 跳过（ID 碰撞保护，防止 UserMsg 被覆盖）
  }

  /** SSE agent_start:为该 agent 起一条新的 streaming 气泡(若已存在则刷新) */
  function startStreaming(convId: string, agentId: string, agentName: string, messageId: string, avatar?: string) {
    streamingConvIds.value.add(convId)
    let inner = streamingMap.value.get(convId)
    if (!inner) {
      inner = new Map()
      streamingMap.value.set(convId, inner)
    }
    inner.set(agentId, {
      messageId,
      agentId,
      agentName,
      avatar,
      blocks: [],
      activity: 'thinking',
      startedAt: new Date(),
      lastEventAt: new Date(),
    })
    // 同时把 thread 卡片(如果有)推到 running
    markThreadRunning(convId, agentId)
    // 触发响应式重建
    streamingMap.value = new Map(streamingMap.value)
  }

  /**
   * SSE block_start:在 agent 的 streaming 气泡内追加一个 block。
   * agentId 不传时取最近的 streaming agent(适配老调用方)。
   */
  function appendBlock(convId: string, block: ContentBlock, agentId?: string) {
    const inner = streamingMap.value.get(convId)
    if (!inner) return
    const targetId = agentId ?? [...inner.keys()].pop()
    if (!targetId) return
    const streaming = inner.get(targetId)
    if (!streaming) return

    const uiBlock = apiBlockToUI(block)
    streaming.blocks = [...streaming.blocks, uiBlock]
    streaming.lastEventAt = new Date()

    // 推断 activity
    if (block.type === 'tool_use') {
      streaming.activity = 'tool'
      streaming.currentTool = block.tool_name
    } else if (block.type === 'text') {
      streaming.activity = 'typing'
    } else if (block.type === 'thinking') {
      streaming.activity = 'thinking'
    }

    // 主 Agent 调度类工具 → 从 input 里抠出 task,本地虚拟出 thread 卡片
    if (block.type === 'tool_use') {
      handleSchedulingTool(convId, block.tool_name, block.input)
    }

    if (block.type === 'approval' && block.status === 'pending') {
      pendingApprovals.value.set(convId, {
        messageId: streaming.messageId,
        blockId: block.block_id,
        action: block.action,
        detail: block.detail,
      })
    }
    streamingMap.value = new Map(streamingMap.value)
  }

  function updateBlock(convId: string, blockId: string, delta: Record<string, unknown>, agentId?: string) {
    const inner = streamingMap.value.get(convId)
    if (!inner) return
    const targets = agentId ? [inner.get(agentId)] : [...inner.values()]
    for (const streaming of targets) {
      if (!streaming) continue
      const idx = streaming.blocks.findIndex(b => {
        const anyB = b as Record<string, unknown>
        return anyB.block_id === blockId
      })
      if (idx === -1) continue
      const block = streaming.blocks[idx] as Record<string, unknown>
      for (const [key, value] of Object.entries(delta)) {
        if (typeof value === 'string' && typeof block[key] === 'string') {
          block[key] = (block[key] as string) + value
        } else {
          block[key] = value
        }
      }
      streaming.blocks = [...streaming.blocks]
      streaming.lastEventAt = new Date()
      // text delta 持续到来 → typing
      if (typeof delta.content === 'string' || typeof delta.text === 'string') {
        streaming.activity = 'typing'
      }
      // 同步 thread 卡片 bytesProduced
      bumpThreadBytes(convId, streaming.agentId, JSON.stringify(delta).length)
      break
    }
    streamingMap.value = new Map(streamingMap.value)
  }

  function finishBlock(convId: string, blockId: string, finalFields?: Record<string, unknown>, agentId?: string) {
    const inner = streamingMap.value.get(convId)
    if (!inner) return
    const targets = agentId ? [inner.get(agentId)] : [...inner.values()]
    for (const streaming of targets) {
      if (!streaming) continue
      const block = streaming.blocks.find(b => {
        const anyB = b as Record<string, unknown>
        return anyB.block_id === blockId
      })
      if (!block) continue
      if (finalFields) {
        const anyBlock = block as Record<string, unknown>
        for (const [key, value] of Object.entries(finalFields)) {
          anyBlock[key] = value
        }
      }
      streaming.blocks = [...streaming.blocks]
      streaming.lastEventAt = new Date()
      // tool_use 完成 → activity 回 idle 等下一步
      if ((block as { type: string }).type === 'tool_use') {
        streaming.activity = 'idle'
        streaming.currentTool = undefined
      }
      break
    }
    streamingMap.value = new Map(streamingMap.value)
  }

  /** 把某个 agent 的 streaming 气泡 commit 进 messageMap,从 streamingMap 移除 */
  function commitAgentStreaming(convId: string, agentId: string) {
    const inner = streamingMap.value.get(convId)
    if (!inner) return
    const streaming = inner.get(agentId)
    if (!streaming) return
    // 空 streaming(blocks=[],被 stop 中断时主 Agent 还没产出任何块)直接丢弃,
    // 不留下空气泡占着列表("主 Agent · just now" 但内容为空的怪现象)。
    // 同样丢弃纯 sentinel 内容（broadcast 模式已读回执，已由 ReadReceiptEvent 处理）。
    const isSentinelOnly = streaming.blocks.length > 0 && streaming.blocks.every(b => {
      if ((b as any).type !== 'text') return false
      const content: string = ((b as any).content ?? '').trim()
      return content === '__READ_RECEIPT__' || content.includes('__READ_RECEIPT__') ||
             content === 'READ_RECEIPT' || content.includes('READ_RECEIPT')
    })
    if (streaming.blocks.length > 0 && !isSentinelOnly) {
      const msgs = [...getMessages(convId)]
      // 从当前会话的 agent 列表中查找头像和名称作为兜底（数据库是真相源）
      const conversationsStore = useConversationsStore()
      const conv = conversationsStore.conversations.find(c => c.id === convId)
      const agentMember = conv?.agents.find(a => a.id === agentId)
      const finalAvatar = agentMember?.avatar ?? streaming.avatar
      const finalName = agentMember?.name ?? streaming.agentName

      const newMsg = {
        id: streaming.messageId,
        type: 'agent' as const,
        agentId: streaming.agentId,
        agentName: finalName,
        avatar: finalAvatar,
        content: (streaming.blocks.find(b => b.type === 'text') as { content: string } | undefined)?.content ?? '',
        timestamp: streaming.startedAt,
        blocks: streaming.blocks,
      }
      // message_appended 先到时已用 agent_reply_id 把落库版本加入 messageMap，
      // 此时 existingIdx 应该找不到（agent_reply_id 与 streaming.messageId 相同）。
      // 万一仍然找到（id 碰撞兜底）→ 不覆盖不重渲染，保留落库版本。
      const existingIdx = msgs.findIndex(m => m.id === streaming.messageId)
      if (existingIdx === -1) {
        msgs.push(newMsg)
        setMessages(convId, msgs)
      }
      // 已存在 → 保持现状，不触发多余渲染
      // broadcast 会话的新消息标记打字流动画
      if (conv?.mode === 'broadcast') {
        newBroadcastMessageIds.value = new Set([...newBroadcastMessageIds.value, streaming.messageId])
      }
    }
    inner.delete(agentId)
    if (inner.size === 0) {
      streamingMap.value.delete(convId)
    }
    streamingMap.value = new Map(streamingMap.value)
    // 同步 thread 卡片 → done
    markThreadDone(convId, agentId)
  }

  /** SSE agent_done:特定 Agent 完成,落库它的气泡 */
  function commitStreamingMessage(convId: string, agentId?: string) {
    if (agentId) {
      commitAgentStreaming(convId, agentId)
      return
    }
    // 没传 agentId(老兼容):commit 所有
    const inner = streamingMap.value.get(convId)
    if (!inner) return
    for (const id of [...inner.keys()]) {
      commitAgentStreaming(convId, id)
    }
  }

  /** SSE agent_error:某 Agent 失败,落库错误状态(简单起见也走 commit) */
  function failStreamingAgent(convId: string, agentId: string, error: string) {
    const inner = streamingMap.value.get(convId)
    const streaming = inner?.get(agentId)
    if (streaming) {
      // 错误信息追加为 text block
      streaming.blocks = [...streaming.blocks, { type: 'text', content: `\n\n[错误] ${error}` }]
    }
    commitAgentStreaming(convId, agentId)
    markThreadError(convId, agentId, error)
  }

  /** SSE round_done:整轮结束,清理所有 streaming + 全部 thread 卡片 */
  function clearRound(convId: string) {
    const inner = streamingMap.value.get(convId)
    if (inner) {
      for (const id of [...inner.keys()]) {
        commitAgentStreaming(convId, id)
      }
    }
    streamingConvIds.value.delete(convId)
    streamingConvIds.value = new Set(streamingConvIds.value)  // 强制触发响应式更新
    // round_done 后 thread 卡片本来该清,但留 5 秒让用户看到完成态会更好
    // MVP 先直接清:
    threadActivitiesMap.value.delete(convId)
    threadActivitiesMap.value = new Map(threadActivitiesMap.value)
  }

  /** 整体 finishStreaming(老接口兼容,通常 agent_error 路径 / 异常断流时调) */
  function finishStreaming(convId: string) {
    const inner = streamingMap.value.get(convId)
    if (inner) {
      for (const id of [...inner.keys()]) {
        commitAgentStreaming(convId, id)
      }
    }
    streamingConvIds.value.delete(convId)
    streamingConvIds.value = new Set(streamingConvIds.value)
    pendingApprovals.value.delete(convId)
    // 同步清掉 thread 调度卡片，否则 workflow 面板会一直显示 running
    threadActivitiesMap.value.delete(convId)
    threadActivitiesMap.value = new Map(threadActivitiesMap.value)
  }

  // ── Thread 调度卡片管理 ──

  function ensureThreadInner(convId: string) {
    let inner = threadActivitiesMap.value.get(convId)
    if (!inner) {
      inner = new Map()
      threadActivitiesMap.value.set(convId, inner)
    }
    return inner
  }

  /**
   * 主 Agent 调度类工具触发本地虚拟 thread 卡片。
   * - dispatch_to_agent input: { agent_id, prompt, blocked_by? }
   *   → 1 条新 thread,status=pending,等 agent_start 触发后转 running
   * - create_task_plan input: { plan: [{id, agent_id, prompt, blocked_by}, ...] }
   *   → 一次创建多条
   * - add_task input: { id, agent_id, prompt, blocked_by? }
   *   → 类似 dispatch
   */
  function handleSchedulingTool(convId: string, toolName: string, input?: Record<string, unknown>) {
    if (!input) return
    const inner = ensureThreadInner(convId)

    if (toolName === 'dispatch_to_agent' || toolName === 'add_task') {
      const agentId = String(input.agent_id ?? '')
      const blockedBy = Array.isArray(input.blocked_by) ? (input.blocked_by as string[]) : []
      if (!agentId) return
      // 没有 thread_id(后端给的),用 agent_id 暂作 key,等 agent_start 来时刷新
      const placeholderId = `pending-${agentId}-${Date.now()}`
      inner.set(placeholderId, {
        threadId: placeholderId,
        agentId,
        agentName: agentId,
        status: 'pending',
        blockedBy,
        bytesProduced: 0,
      })
    } else if (toolName === 'create_task_plan') {
      const plan = Array.isArray(input.plan) ? (input.plan as Record<string, unknown>[]) : []
      for (const task of plan) {
        const tid = String(task.id ?? `task-${Date.now()}-${Math.random()}`)
        const agentId = String(task.agent_id ?? '')
        const blockedBy = Array.isArray(task.blocked_by) ? (task.blocked_by as string[]) : []
        inner.set(tid, {
          threadId: tid,
          agentId,
          agentName: agentId,
          status: 'pending',
          blockedBy,
          bytesProduced: 0,
        })
      }
    }
    threadActivitiesMap.value = new Map(threadActivitiesMap.value)
  }

  /** agent_start 触发:把 pending 的 placeholder 升级成 running(按 agentId 匹配) */
  function markThreadRunning(convId: string, agentId: string) {
    const inner = threadActivitiesMap.value.get(convId)
    if (!inner) return
    // 优先匹配同 agentId 且 status=pending 的(create_task_plan 创建的卡片)
    for (const [, t] of inner) {
      if (t.agentId === agentId && t.status === 'pending') {
        t.status = 'running'
        t.startedAt = new Date()
        threadActivitiesMap.value = new Map(threadActivitiesMap.value)
        return
      }
    }
    // 都没找到说明是 dispatch_to_agent 那种 placeholder,新建一条 running
    const inner2 = ensureThreadInner(convId)
    const tid = `running-${agentId}-${Date.now()}`
    inner2.set(tid, {
      threadId: tid,
      agentId,
      agentName: agentId,
      status: 'running',
      blockedBy: [],
      bytesProduced: 0,
      startedAt: new Date(),
    })
    threadActivitiesMap.value = new Map(threadActivitiesMap.value)
  }

  function markThreadDone(convId: string, agentId: string) {
    const inner = threadActivitiesMap.value.get(convId)
    if (!inner) return
    for (const [, t] of inner) {
      if (t.agentId === agentId && t.status === 'running') {
        t.status = 'done'
        t.finishedAt = new Date()
        threadActivitiesMap.value = new Map(threadActivitiesMap.value)
        return
      }
    }
  }

  function markThreadError(convId: string, agentId: string, errorMessage: string) {
    const inner = threadActivitiesMap.value.get(convId)
    if (!inner) return
    for (const [, t] of inner) {
      if (t.agentId === agentId && (t.status === 'running' || t.status === 'pending')) {
        t.status = 'error'
        t.finishedAt = new Date()
        t.errorMessage = errorMessage
        threadActivitiesMap.value = new Map(threadActivitiesMap.value)
        return
      }
    }
  }

  function bumpThreadBytes(convId: string, agentId: string, delta: number) {
    const inner = threadActivitiesMap.value.get(convId)
    if (!inner) return
    for (const [, t] of inner) {
      if (t.agentId === agentId && t.status === 'running') {
        t.bytesProduced += delta
        return
      }
    }
  }

  // ── 审批 ──

  function resolveApproval(convId: string, messageId: string, blockId: string, decision: 'approved' | 'rejected', reason?: string) {
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

    // streaming 气泡里也要更新
    const inner = streamingMap.value.get(convId)
    if (inner) {
      for (const streaming of inner.values()) {
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
      streamingMap.value = new Map(streamingMap.value)
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

  function addReadReceipt(messageId: string, agentId: string, agentName: string, agentAvatar?: string) {
    const existing = readReceiptsMap.value.get(messageId) ?? []
    if (existing.some(r => r.agentId === agentId)) return
    readReceiptsMap.value.set(messageId, [...existing, { agentId, agentName, agentAvatar }])
    readReceiptsMap.value = new Map(readReceiptsMap.value)
  }

  function getReadReceipts(messageId: string) {
    return readReceiptsMap.value.get(messageId) ?? []
  }

  function consumeNewBroadcastMessage(messageId: string) {
    if (!newBroadcastMessageIds.value.has(messageId)) return false
    const next = new Set(newBroadcastMessageIds.value)
    next.delete(messageId)
    newBroadcastMessageIds.value = next
    return true
  }

  return {
    // State
    messageMap,
    streamingMap,
    streamingConvIds,
    threadActivitiesMap,
    pendingApprovals,
    readReceiptsMap,
    newBroadcastMessageIds,

    // Getters
    getMessages,
    setMessages,
    getLastMessageId,
    isStreamingFor,
    getStreamingAgents,
    getAgentStreaming,
    getStreamingMessage,
    getThreadActivities,
    getPendingApproval,
    getInputDraft,
    setInputDraft,
    getInputHtmlDraft,
    getReplyPreview,
    setReplyPreview,
    currentMessages,
    isAnyStreaming,
    getReadReceipts,

    // Actions
    loadFromAPI,
    prependMessages,
    addUserMessage,
    confirmUserMessage,
    appendPersistedMessage,
    startStreaming,
    appendBlock,
    updateBlock,
    finishBlock,
    commitStreamingMessage,
    failStreamingAgent,
    finishStreaming,
    clearRound,
    resolveApproval,
    updateReaction,
    addReadReceipt,
    consumeNewBroadcastMessage,
  }
})
