import { defineStore } from 'pinia'
import { ref } from 'vue'
import { workflowsApi, type WorkflowThreadDTO } from '@/api/workflows'

export type ThreadStatus = 'init' | 'running' | 'suspended' | 'done' | 'error' | 'cancelled'

export interface WorkflowBlock {
  blockId: string
  type: string           // 'text' | 'tool_use' | 'thinking' | 'code' | ...
  toolName?: string      // only for tool_use
  toolInput?: Record<string, unknown>  // tool_use 的入参 JSON
  content?: string       // text/thinking block 的预览内容
  // code block 字段
  language?: string
  code?: string
  filename?: string
  status: 'running' | 'done'
  startedAt: number
  finishedAt?: number
}

export interface WorkflowThread {
  threadId: string
  agentId: string
  agentName: string
  avatar?: string
  messageId: string
  status: ThreadStatus
  blocks: WorkflowBlock[]
  startedAt: number
  finishedAt?: number
  error?: string
  tokensInput?: number
  tokensOutput?: number
}

/** 历史 workflow（已落库的某轮快照） */
export interface WorkflowSnapshot {
  id: string
  triggerMessageId?: string
  threads: WorkflowThread[]
  createdAt: number
}

export const useWorkflowStore = defineStore('workflow', () => {
  // per-conversation 当前轮 streaming 中的 thread 列表（活跃数据）
  const threadMap = ref<Map<string, WorkflowThread[]>>(new Map())
  // per-conversation 历史 workflow 列表（已持久化的过往轮次，按 createdAt 升序，最新在末尾）
  const historyMap = ref<Map<string, WorkflowSnapshot[]>>(new Map())
  // 加载状态去重
  const loadingMap = ref<Map<string, boolean>>(new Map())
  // per-conversation 本轮 trigger user_message_id（sendMessage 时由 useChat 设置，
  // round_done persist 时取出并清空）
  const triggerMessageMap = ref<Map<string, string>>(new Map())
  // 标记某 conv 的下一次 persistCurrent 应跳过（stop 路径专用：cancelled 的轮次不入库）
  const skipNextPersist = ref<Set<string>>(new Set())

  function getThreads(convId: string): WorkflowThread[] {
    return threadMap.value.get(convId) ?? []
  }

  /** 历史 workflow 列表（最新在数组末尾，前端按数组顺序渲染即"最新在下"） */
  function getHistory(convId: string): WorkflowSnapshot[] {
    return historyMap.value.get(convId) ?? []
  }

  function _getOrCreate(convId: string): WorkflowThread[] {
    if (!threadMap.value.has(convId)) {
      threadMap.value.set(convId, [])
    }
    return threadMap.value.get(convId)!
  }

  // ── SSE handlers ──

  function onAgentStart(convId: string, payload: {
    agentId: string
    agentName: string
    agentAvatar?: string
    threadId: string
    messageId: string
    avatar?: string
  }) {
    const threads = _getOrCreate(convId)
    const existing = threads.find(t => t.threadId === payload.threadId)
    if (existing) {
      // init → running 状态升级
      existing.status = 'running'
      existing.startedAt = Date.now()
      // 补回 avatar（如果之前没有）
      if (!existing.avatar && payload.avatar) {
        existing.avatar = payload.avatar
      }
      threadMap.value.set(convId, [...threads])
      return
    }
    threads.push({
      threadId: payload.threadId,
      agentId: payload.agentId,
      agentName: payload.agentName,
      avatar: payload.avatar,
      messageId: payload.messageId,
      status: 'running',
      blocks: [],
      startedAt: Date.now(),
    })
    threadMap.value.set(convId, [...threads])
  }

  function onBlockStart(convId: string, threadId: string, block: {
    blockId: string
    type: string
    toolName?: string
    toolInput?: Record<string, unknown>
    content?: string
    language?: string
    code?: string
    filename?: string
  }) {
    const threads = getThreads(convId)
    const thread = threads.find(t => t.threadId === threadId)
    if (!thread) return
    thread.blocks.push({
      blockId: block.blockId,
      type: block.type,
      toolName: block.toolName,
      toolInput: block.toolInput,
      content: block.content,
      language: block.language,
      code: block.code,
      filename: block.filename,
      status: 'running',
      startedAt: Date.now(),
    })
    threadMap.value.set(convId, [...threads])
  }

  function onBlockStop(convId: string, threadId: string, blockId: string, finalContent?: string) {
    const threads = getThreads(convId)
    const thread = threads.find(t => t.threadId === threadId)
    if (!thread) return
    const block = thread.blocks.find(b => b.blockId === blockId)
    if (block) {
      block.status = 'done'
      block.finishedAt = Date.now()
      if (finalContent) block.content = finalContent
    }
    threadMap.value.set(convId, [...threads])
  }

  function onBlockDelta(convId: string, threadId: string, blockId: string, delta: Record<string, unknown>) {
    const threads = getThreads(convId)
    const thread = threads.find(t => t.threadId === threadId)
    if (!thread) return
    const block = thread.blocks.find(b => b.blockId === blockId)
    if (block && typeof delta.content === 'string') {
      block.content = (block.content ?? '') + delta.content
    }
    // 不触发 threadMap.set 避免频繁重渲（delta 高频），content 是引用更新
  }

  function onAgentDone(convId: string, threadId: string, tokens?: {
    input?: number
    output?: number
  }) {
    const threads = getThreads(convId)
    const thread = threads.find(t => t.threadId === threadId)
    if (!thread) return
    thread.status = 'done'
    thread.finishedAt = Date.now()
    if (tokens?.input != null) thread.tokensInput = tokens.input
    if (tokens?.output != null) thread.tokensOutput = tokens.output
    threadMap.value.set(convId, [...threads])
  }

  function onAgentError(convId: string, threadId: string, error: string) {
    const threads = getThreads(convId)
    const thread = threads.find(t => t.threadId === threadId)
    if (!thread) return
    // "cancelled" error 走 cancelled 状态
    thread.status = error === 'cancelled' ? 'cancelled' : 'error'
    thread.finishedAt = Date.now()
    if (error !== 'cancelled') thread.error = error
    threadMap.value.set(convId, [...threads])
  }

  function clearRound(convId: string) {
    threadMap.value.set(convId, [])
  }

  /**
   * round_done 后落库：把当前轮内存里的 threads POST 到后端。
   * 落库成功后追加到 historyMap 末尾（最新在下），并清空当前轮 threadMap。
   *
   * 跳过场景：
   * - threads 为空（没有任何活动）
   * - skipNextPersist 已标记（stop 路径：cancelled 的轮次不应入库）
   *
   * 失败时保留 threadMap：网络抖动等情况下，用户至少能看到刚才的 streaming 数据，
   * 而不是 workflow 凭空消失。下一轮 round_done 会重新尝试持久化前面累积的状态。
   */
  async function persistCurrent(convId: string, triggerMessageId?: string) {
    // stop 路径已标记跳过：清状态但不落库
    if (skipNextPersist.value.has(convId)) {
      skipNextPersist.value.delete(convId)
      threadMap.value.set(convId, [])
      triggerMessageMap.value.delete(convId)
      return
    }

    const threads = getThreads(convId)
    if (threads.length === 0) {
      triggerMessageMap.value.delete(convId)
      return
    }

    const trigger = triggerMessageId ?? triggerMessageMap.value.get(convId)
    try {
      const saved = await workflowsApi.save({
        conversation_id: convId,
        trigger_message_id: trigger,
        threads: threads as unknown as WorkflowThreadDTO[],
      })
      // 把刚保存的当成一份历史 snapshot 追加到末尾（最新在下）
      const list = historyMap.value.get(convId) ?? []
      list.push({
        id: saved.id,
        triggerMessageId: saved.trigger_message_id,
        threads: saved.threads as unknown as WorkflowThread[],
        createdAt: new Date(saved.created_at).getTime(),
      })
      historyMap.value.set(convId, [...list])
      // 成功才清掉当前轮 + trigger 关联
      threadMap.value.set(convId, [])
      triggerMessageMap.value.delete(convId)
    } catch (e) {
      console.warn('[workflow] persist failed, keeping threadMap for retry on next round', e)
      // 失败时不清 threadMap，让用户至少还能看到本轮内容
    }
  }

  /** sendMessage 后由 useChat 调用，记录"本轮 workflow 由哪条用户消息触发" */
  function setCurrentTrigger(convId: string, messageId: string) {
    triggerMessageMap.value.set(convId, messageId)
  }

  /** stop 路径调用：标记下一次 persistCurrent 跳过（cancelled 轮次不入库） */
  function skipNextPersistFor(convId: string) {
    skipNextPersist.value.add(convId)
  }

  /**
   * 进入会话时调：拉最近 N 份历史 workflow，按 createdAt 升序排到 historyMap。
   * 后端默认按 created_at DESC 返回，前端 reverse() 后"最新在下"。
   *
   * 注意：当前是一次性拉 limit 条全量替换 historyMap。如需分页加载更多历史，
   * 不能简单地把后续页 reverse() 后 push 进 historyMap——后续页拿到的是更早的
   * 数据，应 reverse 后 unshift 到数组开头。改分页前请同步调整这里的合并逻辑。
   */
  async function loadHistory(convId: string, limit = 20) {
    if (loadingMap.value.get(convId)) return
    loadingMap.value.set(convId, true)
    try {
      const list = await workflowsApi.list(convId, { limit })
      // 后端 DESC（最新在前）→ reverse 后 ASC（最新在后），符合"最新在下"的展示
      const snapshots: WorkflowSnapshot[] = list.reverse().map(w => ({
        id: w.id,
        triggerMessageId: w.trigger_message_id,
        threads: w.threads as unknown as WorkflowThread[],
        createdAt: new Date(w.created_at).getTime(),
      }))
      historyMap.value.set(convId, snapshots)
    } catch (e) {
      console.warn('[workflow] load history failed', e)
    } finally {
      loadingMap.value.set(convId, false)
    }
  }

  /** 切走会话时清掉缓存，避免误显示别的会话历史 */
  function resetForConversation(convId: string) {
    threadMap.value.set(convId, [])
    historyMap.value.set(convId, [])
  }

  /**
   * stop 时被调:把所有还在 running/init/suspended 的 thread 标 cancelled,
   * 同步把它们尚未结束的 block.status 也标 done(避免转圈)。
   * 已 done/error/cancelled 的不动,保留本轮历史给用户回看。
   */
  function markActiveAsCancelled(convId: string) {
    const threads = getThreads(convId)
    let changed = false
    for (const t of threads) {
      if (t.status === 'running' || t.status === 'init' || t.status === 'suspended') {
        t.status = 'cancelled'
        t.finishedAt = Date.now()
        changed = true
        for (const b of t.blocks) {
          if (b.status === 'running') {
            b.status = 'done'
            b.finishedAt = Date.now()
          }
        }
      }
    }
    if (changed) {
      threadMap.value.set(convId, [...threads])
    }
  }

  return {
    threadMap,
    historyMap,
    getThreads,
    getHistory,
    onAgentStart,
    onBlockStart,
    onBlockStop,
    onBlockDelta,
    onAgentDone,
    onAgentError,
    clearRound,
    markActiveAsCancelled,
    persistCurrent,
    loadHistory,
    resetForConversation,
    setCurrentTrigger,
    skipNextPersistFor,
  }
})
