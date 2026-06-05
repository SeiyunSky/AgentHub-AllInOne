<template>
  <div class="h-full flex flex-col overflow-hidden">

    <!-- Empty state -->
    <div v-if="threads.length === 0 && history.length === 0" class="flex-1 flex flex-col items-center justify-center gap-4 px-6 text-center">
      <div class="w-16 h-16 rounded-2xl flex items-center justify-center"
           style="background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(139,92,246,0.08));">
        <el-icon :size="28" class="text-brand/40"><Share /></el-icon>
      </div>
      <div>
        <p class="text-[13px] font-semibold text-on-surface-variant">等待 Agent 运行</p>
        <p class="text-[11px] text-on-surface-variant/60 mt-1">发送消息后将在此处实时展示执行流程</p>
      </div>
    </div>

    <!-- Thread list（历史 + 当前轮，最新在下） -->
    <div v-else class="flex-1 overflow-y-auto custom-scrollbar px-4 py-4 space-y-2">

      <!-- Stats bar (only for current round) -->
      <div v-if="threads.length > 0" class="flex items-center gap-3 px-1 mb-3">
        <span class="text-[11px] text-on-surface-variant/60">
          {{ threads.length }} 个 Agent
        </span>
        <span class="text-on-surface-variant/30">·</span>
        <span class="text-[11px] text-on-surface-variant/60">
          {{ doneCount }} 完成
          <template v-if="errorCount"> · <span class="text-error">{{ errorCount }} 失败</span></template>
          <template v-if="cancelledCount"> · <span class="text-on-surface-variant/40">{{ cancelledCount }} 已取消</span></template>
        </span>
        <span v-if="totalTokens > 0" class="ml-auto text-[11px] text-on-surface-variant/50 font-mono">
          {{ formatTokens(totalTokens) }} tok
        </span>
      </div>

      <!-- 历史 workflow snapshots（按 createdAt 升序，最新在末尾） -->
      <template v-for="snap in history" :key="snap.id">
        <div class="flex items-center gap-2 px-2 py-1">
          <div class="flex-1 h-px bg-outline-variant/40"></div>
          <span class="text-[10px] text-on-surface-variant/50 font-medium shrink-0">
            {{ formatSnapshotTime(snap.createdAt) }}
          </span>
          <div class="flex-1 h-px bg-outline-variant/40"></div>
        </div>
        <div v-for="thread in snap.threads" :key="`${snap.id}-${thread.threadId}`"
          class="workflow-thread-card rounded-2xl border overflow-hidden"
          :class="threadCardClass(thread.status)"
        >
          <div class="flex items-center gap-3 px-4 py-3 cursor-pointer select-none"
               :class="threadHeaderClass(thread.status)"
               @click="toggleCollapsed(`${snap.id}-${thread.threadId}`, isCollapsedKey(`${snap.id}-${thread.threadId}`, thread.status))">
            <div class="w-8 h-8 rounded-xl flex items-center justify-center text-white text-[12px] font-bold shrink-0 overflow-hidden"
                 :style="thread.avatar ? undefined : { background: agentGradient(thread.agentName) }">
              <img v-if="thread.avatar" :src="thread.avatar" :alt="thread.agentName" class="w-full h-full object-cover" />
              <template v-else>{{ thread.agentName.charAt(0).toUpperCase() }}</template>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-[13px] font-semibold text-on-surface truncate">{{ thread.agentName }}</span>
                <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full shrink-0" :class="statusBadgeClass(thread.status)">
                  {{ statusLabel(thread.status) }}
                </span>
              </div>
              <div class="text-[11px] text-on-surface-variant mt-0.5 flex items-center gap-1.5 flex-wrap">
                <template v-if="thread.tokensInput != null || thread.tokensOutput != null">
                  <span class="font-mono">↑{{ thread.tokensInput ?? 0 }} ↓{{ thread.tokensOutput ?? 0 }}</span>
                </template>
              </div>
            </div>
            <div class="shrink-0 flex items-center gap-1.5">
              <el-icon v-if="thread.status === 'done'" class="text-success" :size="18"><CircleCheckFilled /></el-icon>
              <el-icon v-else-if="thread.status === 'error'" class="text-error" :size="18"><CircleCloseFilled /></el-icon>
              <el-icon v-else-if="thread.status === 'cancelled'" class="text-on-surface-variant/40" :size="18"><RemoveFilled /></el-icon>
              <el-icon
                class="text-on-surface-variant/40 transition-transform duration-200 ml-0.5"
                :class="{ 'rotate-180': !isCollapsedKey(`${snap.id}-${thread.threadId}`, thread.status) }"
                :size="14"
              ><ArrowDown /></el-icon>
            </div>
          </div>
          <Transition name="collapse">
            <div v-show="!isCollapsedKey(`${snap.id}-${thread.threadId}`, thread.status)" v-if="thread.blocks.length > 0" class="px-4 py-2 space-y-1 border-t border-outline-variant/30">
              <div v-for="block in thread.blocks" :key="block.blockId" class="flex items-start gap-2 py-0.5 group">
                <div class="w-1.5 h-1.5 rounded-full shrink-0 mt-1.5" :class="blockDotClass(block)"></div>
                <el-icon :size="12" class="shrink-0 mt-1" :class="blockIconClass(block)">
                  <component :is="blockIcon(block)" />
                </el-icon>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <span class="text-[11px] text-on-surface-variant font-medium">{{ blockLabel(block) }}</span>
                  </div>
                  <p v-if="(block.type === 'text' || block.type === 'thinking') && block.content"
                    class="text-[10px] text-on-surface-variant/50 mt-0.5 line-clamp-2 leading-relaxed">
                    {{ block.content }}
                  </p>
                </div>
              </div>
            </div>
          </Transition>
        </div>
      </template>

      <!-- 当前轮（streaming 中或刚结束尚未持久化）—— 始终在最下方 -->
      <template v-if="threads.length > 0">
        <div v-if="history.length > 0" class="flex items-center gap-2 px-2 py-1">
          <div class="flex-1 h-px bg-brand/40"></div>
          <span class="text-[10px] text-brand font-medium shrink-0">本轮</span>
          <div class="flex-1 h-px bg-brand/40"></div>
        </div>
        <TransitionGroup name="thread-enter">
          <div
            v-for="(thread, idx) in threads"
            :key="thread.threadId"
            class="workflow-thread-card rounded-2xl border overflow-hidden"
            :class="threadCardClass(thread.status)"
            :style="{ animationDelay: `${idx * 0.05}s` }"
          >
            <!-- Card header -->
            <div class="flex items-center gap-3 px-4 py-3 cursor-pointer select-none"
                 :class="threadHeaderClass(thread.status)"
                 @click="toggleCollapsed(thread.threadId, isCollapsed(thread))">
              <div
                class="w-8 h-8 rounded-xl flex items-center justify-center text-white text-[12px] font-bold shrink-0 relative overflow-hidden"
                :style="thread.avatar ? undefined : { background: agentGradient(thread.agentName) }"
              >
                <img v-if="thread.avatar" :src="thread.avatar" :alt="thread.agentName" class="w-full h-full object-cover" />
                <template v-else>{{ thread.agentName.charAt(0).toUpperCase() }}</template>
                <span v-if="thread.status === 'init'"
                  class="absolute inset-0 rounded-xl border-2 border-white/40 animate-ping" />
              </div>

              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="text-[13px] font-semibold text-on-surface truncate">{{ thread.agentName }}</span>
                  <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full shrink-0" :class="statusBadgeClass(thread.status)">
                    {{ statusLabel(thread.status) }}
                  </span>
                </div>
                <div class="text-[11px] text-on-surface-variant mt-0.5 flex items-center gap-1.5 flex-wrap">
                  <span v-if="thread.status !== 'init'" class="font-mono">{{ elapsedTime(thread) }}</span>
                  <template v-if="thread.tokensInput != null || thread.tokensOutput != null">
                    <span class="text-on-surface-variant/40">·</span>
                    <span class="font-mono">↑{{ thread.tokensInput ?? 0 }} ↓{{ thread.tokensOutput ?? 0 }}</span>
                  </template>
                </div>
              </div>

              <div class="shrink-0 flex items-center gap-1.5">
                <div v-if="thread.status === 'init'" class="w-5 h-5 rounded-full border-2 border-on-surface-variant/30 border-dashed"></div>
                <div v-else-if="thread.status === 'running'" class="w-5 h-5 rounded-full border-2 border-brand border-t-transparent animate-spin"></div>
                <div v-else-if="thread.status === 'suspended'" class="w-5 h-5 rounded-full border-2 border-warning flex items-center justify-center">
                  <div class="w-1.5 h-1.5 rounded-full bg-warning"></div>
                </div>
                <el-icon v-else-if="thread.status === 'done'" class="text-success" :size="18"><CircleCheckFilled /></el-icon>
                <el-icon v-else-if="thread.status === 'error'" class="text-error" :size="18"><CircleCloseFilled /></el-icon>
                <el-icon v-else-if="thread.status === 'cancelled'" class="text-on-surface-variant/40" :size="18"><RemoveFilled /></el-icon>
                <el-icon
                  class="text-on-surface-variant/40 transition-transform duration-200 ml-0.5"
                  :class="{ 'rotate-180': !isCollapsed(thread) }"
                  :size="14"
                ><ArrowDown /></el-icon>
              </div>
            </div>

            <Transition name="collapse">
              <div v-show="!isCollapsed(thread)" v-if="thread.blocks.length > 0" class="px-4 py-2 space-y-1 border-t border-outline-variant/30">
              <div v-for="block in thread.blocks" :key="block.blockId"
                class="flex items-start gap-2 py-0.5 group"
              >
                <div class="w-1.5 h-1.5 rounded-full shrink-0 mt-1.5" :class="blockDotClass(block)"></div>
                <el-icon :size="12" class="shrink-0 mt-1" :class="blockIconClass(block)">
                  <component :is="blockIcon(block)" />
                </el-icon>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <span class="text-[11px] text-on-surface-variant font-medium">{{ blockLabel(block) }}</span>
                    <span v-if="block.finishedAt" class="text-[10px] text-on-surface-variant/40 font-mono">
                      {{ ((block.finishedAt - block.startedAt) / 1000).toFixed(1) }}s
                    </span>
                    <div v-else-if="block.status === 'running'" class="w-2.5 h-2.5 rounded-full border border-brand border-t-transparent animate-spin shrink-0"></div>
                    <span v-if="block.type === 'code' && block.language"
                      class="text-[9px] font-mono px-1 py-0.5 rounded bg-sky-400/15 text-sky-400/80">
                      {{ block.language }}
                    </span>
                    <span v-if="block.type === 'code' && block.filename"
                      class="text-[9px] font-mono text-on-surface-variant/40 truncate max-w-[120px]">
                      {{ block.filename }}
                    </span>
                  </div>
                  <p v-if="(block.type === 'text' || block.type === 'thinking') && block.content"
                    class="text-[10px] text-on-surface-variant/50 mt-0.5 line-clamp-2 leading-relaxed">
                    {{ block.content }}
                  </p>
                  <div v-if="block.type === 'tool_use' && block.toolInput"
                    class="mt-0.5 rounded-lg bg-surface-container-low/80 border border-outline-variant/20 overflow-hidden">
                    <pre class="text-[9px] text-on-surface-variant/50 font-mono px-2 py-1.5 overflow-x-auto leading-relaxed max-h-[80px] overflow-y-auto">{{ formatToolInput(block.toolInput) }}</pre>
                  </div>
                  <div v-if="block.type === 'code' && block.code"
                    class="mt-0.5 rounded-lg bg-surface-container-low/80 border border-outline-variant/20 overflow-hidden">
                    <pre class="text-[9px] text-sky-400/70 font-mono px-2 py-1.5 overflow-x-auto leading-relaxed max-h-[100px] overflow-y-auto">{{ block.code }}</pre>
                  </div>
                </div>
              </div>
            </div>
            </Transition>

            <Transition name="collapse">
              <div v-show="!isCollapsed(thread)" v-if="thread.status === 'init'" class="px-4 py-2 border-t border-outline-variant/20">
                <p class="text-[11px] text-on-surface-variant/40 flex items-center gap-1.5">
                  <span class="inline-block w-1 h-1 rounded-full bg-on-surface-variant/30 animate-bounce"></span>
                  等待依赖任务完成后启动
                </p>
              </div>
            </Transition>

            <Transition name="collapse">
              <div v-show="!isCollapsed(thread)" v-if="thread.status === 'suspended'" class="px-4 py-2 border-t border-warning/20 bg-warning/5">
                <p class="text-[11px] text-warning flex items-center gap-1.5">
                  <el-icon :size="11"><WarningFilled /></el-icon>
                  等待用户审批
                </p>
              </div>
            </Transition>

            <Transition name="collapse">
              <div v-show="!isCollapsed(thread)" v-if="thread.error" class="px-4 py-2.5 border-t border-error/20 bg-error/5">
                <p class="text-[11px] text-error/80 leading-relaxed break-words">{{ thread.error }}</p>
              </div>
            </Transition>

            <Transition name="collapse">
              <div v-show="!isCollapsed(thread)" v-if="thread.status === 'cancelled'" class="px-4 py-2 border-t border-outline-variant/20">
                <p class="text-[11px] text-on-surface-variant/40">已取消</p>
              </div>
            </Transition>
          </div>
        </TransitionGroup>

        <div v-if="isRoundDone" class="flex items-center gap-2 px-2 py-1 mt-2">
          <div class="flex-1 h-px bg-outline-variant/60"></div>
          <span class="text-[10px] text-on-surface-variant/40 font-medium shrink-0">本轮完成</span>
          <div class="flex-1 h-px bg-outline-variant/60"></div>
        </div>
      </template>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import {
  Share, CircleCheckFilled, CircleCloseFilled, RemoveFilled,
  WarningFilled, ChatLineRound, Tools, Document, Picture, View, Promotion, ArrowDown,
} from '@element-plus/icons-vue'
import { useWorkflowStore, type WorkflowThread, type WorkflowBlock } from '@/stores/workflow'
import { useConversationsStore } from '@/stores/conversations'
import { useAgentsStore } from '@/stores/agents'

const workflowStore = useWorkflowStore()
const conversationsStore = useConversationsStore()
const agentsStore = useAgentsStore()

const collapsed = ref<Map<string, boolean>>(new Map())

function isCollapsed(thread: WorkflowThread): boolean {
  if (collapsed.value.has(thread.threadId)) {
    return collapsed.value.get(thread.threadId)!
  }
  return thread.status !== 'running'
}

function isCollapsedKey(key: string, status: string): boolean {
  if (collapsed.value.has(key)) {
    return collapsed.value.get(key)!
  }
  // 历史卡片默认折叠（除非用户点开）
  return status !== 'running'
}

function toggleCollapsed(key: string, current: boolean) {
  collapsed.value = new Map(collapsed.value).set(key, !current)
}

const convId = computed(() => conversationsStore.currentId ?? '')
const threads = computed(() => workflowStore.threadMap.get(convId.value) ?? [])
const history = computed(() => workflowStore.historyMap.get(convId.value) ?? [])

// 切会话时：清掉离开会话的 streaming 残留 + 加载新会话历史。
// 离开时若上一会话还在 streaming，threadMap 会被卡在 running 状态没人清——
// 用户切回时显示陈旧 streaming 气泡。这里在 oldId 上调 clearRound 兜底。
watch(convId, (newId, oldId) => {
  if (oldId && oldId !== newId) {
    workflowStore.clearRound(oldId)
  }
  if (newId) {
    workflowStore.loadHistory(newId)
  }
}, { immediate: true })

const isRoundDone = computed(() =>
  threads.value.length > 0 && threads.value.every(t =>
    t.status === 'done' || t.status === 'error' || t.status === 'cancelled'
  ),
)

const doneCount = computed(() => threads.value.filter(t => t.status === 'done').length)
const errorCount = computed(() => threads.value.filter(t => t.status === 'error').length)
const cancelledCount = computed(() => threads.value.filter(t => t.status === 'cancelled').length)
const totalTokens = computed(() =>
  threads.value.reduce((sum, t) => sum + (t.tokensInput ?? 0) + (t.tokensOutput ?? 0), 0)
)

// Tick every 100ms to refresh elapsed timers for running threads
const tick = ref(Date.now())
let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  agentsStore.loadAgents()
  timer = setInterval(() => { tick.value = Date.now() }, 100)
})
onUnmounted(() => { if (timer) clearInterval(timer) })

// ── Display helpers ──

const GRADIENTS = [
  'linear-gradient(135deg, #6366f1, #8b5cf6)',
  'linear-gradient(135deg, #3b82f6, #06b6d4)',
  'linear-gradient(135deg, #10b981, #059669)',
  'linear-gradient(135deg, #f59e0b, #ef4444)',
  'linear-gradient(135deg, #ec4899, #8b5cf6)',
]
function agentGradient(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) & 0xffffffff
  return GRADIENTS[Math.abs(hash) % GRADIENTS.length]
}

/** 从 agentsStore → conversationStore 逐级 fallback 获取头像 */
function getAgentAvatar(thread: WorkflowThread): string | undefined {
  // 1. 优先从 agentsStore 获取（全局 agent 列表）
  const fromStore = agentsStore.agents.find((a: { id: string; avatar?: string }) => a.id === thread.agentId)?.avatar
  if (fromStore) return fromStore

  // 2. fallback 到当前会话的 agent 成员列表
  const conv = conversationsStore.currentConversation
  if (conv) {
    const fromConv = conv.agents.find((a: { id: string; avatar?: string }) => a.id === thread.agentId)?.avatar
    if (fromConv) return fromConv
  }

  return undefined
}

function formatTokens(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

function elapsedTime(thread: WorkflowThread): string {
  if (thread.startedAt == null) return ''
  const end = thread.finishedAt ?? tick.value
  return ((end - thread.startedAt) / 1000).toFixed(1) + 's'
}

function formatSnapshotTime(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function statusLabel(s: WorkflowThread['status']) {
  return {
    init: 'WAITING',
    running: 'RUNNING',
    suspended: 'PAUSED',
    done: 'DONE',
    error: 'ERROR',
    cancelled: 'CANCELLED',
  }[s] ?? s.toUpperCase()
}

function threadCardClass(s: WorkflowThread['status']) {
  if (s === 'running')   return 'border-brand/40 shadow-[0_0_16px_rgba(99,102,241,0.1)]'
  if (s === 'done')      return 'border-success/30'
  if (s === 'error')     return 'border-error/30'
  if (s === 'suspended') return 'border-warning/40'
  if (s === 'cancelled') return 'border-outline-variant/30 opacity-60'
  return 'border-outline-variant/40'  // init
}

function threadHeaderClass(s: WorkflowThread['status']) {
  if (s === 'running')   return 'bg-gradient-to-r from-brand/8 to-violet-500/5'
  if (s === 'done')      return 'bg-success/5'
  if (s === 'error')     return 'bg-error/5'
  if (s === 'suspended') return 'bg-warning/8'
  if (s === 'cancelled') return 'bg-surface-container-low/40'
  return 'bg-surface-container-low/60'  // init
}

function statusBadgeClass(s: WorkflowThread['status']) {
  if (s === 'running')   return 'bg-brand/15 text-brand'
  if (s === 'done')      return 'bg-success/15 text-success'
  if (s === 'error')     return 'bg-error/15 text-error'
  if (s === 'suspended') return 'bg-warning/15 text-warning'
  if (s === 'cancelled') return 'bg-on-surface-variant/10 text-on-surface-variant/50'
  return 'bg-on-surface-variant/10 text-on-surface-variant/50'  // init
}

const BLOCK_LABELS: Record<string, string> = {
  text: '输出文本',
  thinking: '思考中',
  tool_use: '',
  code: '生成代码',
  image: '图像',
  approval: '等待审批',
  deployment: '部署',
  artifacts: '产出物',
}

function blockLabel(block: WorkflowBlock): string {
  if (block.type === 'tool_use') return block.toolName ?? 'tool'
  return BLOCK_LABELS[block.type] ?? block.type
}

function formatToolInput(input: Record<string, unknown>): string {
  try {
    return JSON.stringify(input, null, 2)
  } catch {
    return String(input)
  }
}

function blockIcon(block: WorkflowBlock) {
  if (block.type === 'tool_use') return Tools
  if (block.type === 'text')     return ChatLineRound
  if (block.type === 'thinking') return View
  if (block.type === 'code')     return Document
  if (block.type === 'image')    return Picture
  if (block.type === 'deployment') return Promotion
  return View
}

function blockDotClass(block: WorkflowBlock): string {
  if (block.status === 'running') return 'bg-brand animate-pulse'
  if (block.type === 'tool_use')  return 'bg-warning/80'
  if (block.type === 'thinking')  return 'bg-violet-400/80'
  if (block.type === 'code')      return 'bg-sky-400/80'
  return 'bg-success/60'
}

function blockIconClass(block: WorkflowBlock): string {
  if (block.status === 'running') return 'text-brand'
  if (block.type === 'tool_use')  return 'text-warning/70'
  if (block.type === 'thinking')  return 'text-violet-400/70'
  if (block.type === 'code')      return 'text-sky-400/70'
  return 'text-on-surface-variant/40'
}
</script>

<style scoped>
.thread-enter-enter-active {
  animation: thread-in 0.35s cubic-bezier(0.16, 1, 0.3, 1) both;
}
.thread-enter-move {
  transition: transform 0.3s ease;
}
@keyframes thread-in {
  from { opacity: 0; transform: translateY(8px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
.workflow-thread-card {
  background: #ffffff;
  transition: box-shadow 0.2s ease, border-color 0.2s ease, opacity 0.2s ease;
}
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.collapse-enter-active,
.collapse-leave-active {
  transition: opacity 0.15s ease;
}
.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
}
</style>
