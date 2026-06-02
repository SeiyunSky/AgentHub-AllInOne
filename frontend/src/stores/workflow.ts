import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ThreadStatus = 'running' | 'done' | 'error'

export interface WorkflowBlock {
  blockId: string
  type: string           // 'text' | 'tool_use' | 'thinking' | 'code' | ...
  toolName?: string      // only for tool_use
  status: 'running' | 'done'
  startedAt: number
  finishedAt?: number
}

export interface WorkflowThread {
  threadId: string
  agentId: string
  agentName: string
  messageId: string
  status: ThreadStatus
  blocks: WorkflowBlock[]
  startedAt: number
  finishedAt?: number
  error?: string
  tokensInput?: number
  tokensOutput?: number
}

export const useWorkflowStore = defineStore('workflow', () => {
  // per-conversation thread list, keyed by convId
  const threadMap = ref<Map<string, WorkflowThread[]>>(new Map())

  function getThreads(convId: string): WorkflowThread[] {
    return threadMap.value.get(convId) ?? []
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
    threadId: string
    messageId: string
  }) {
    const threads = _getOrCreate(convId)
    // avoid duplicates on reconnect
    if (threads.find(t => t.threadId === payload.threadId)) return
    threads.push({
      threadId: payload.threadId,
      agentId: payload.agentId,
      agentName: payload.agentName,
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
  }) {
    const threads = getThreads(convId)
    const thread = threads.find(t => t.threadId === threadId)
    if (!thread) return
    thread.blocks.push({
      blockId: block.blockId,
      type: block.type,
      toolName: block.toolName,
      status: 'running',
      startedAt: Date.now(),
    })
    threadMap.value.set(convId, [...threads])
  }

  function onBlockStop(convId: string, threadId: string, blockId: string) {
    const threads = getThreads(convId)
    const thread = threads.find(t => t.threadId === threadId)
    if (!thread) return
    const block = thread.blocks.find(b => b.blockId === blockId)
    if (block) {
      block.status = 'done'
      block.finishedAt = Date.now()
    }
    threadMap.value.set(convId, [...threads])
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
    thread.status = 'error'
    thread.finishedAt = Date.now()
    thread.error = error
    threadMap.value.set(convId, [...threads])
  }

  function clearRound(convId: string) {
    threadMap.value.set(convId, [])
  }

  return {
    threadMap,
    getThreads,
    onAgentStart,
    onBlockStart,
    onBlockStop,
    onAgentDone,
    onAgentError,
    clearRound,
  }
})
