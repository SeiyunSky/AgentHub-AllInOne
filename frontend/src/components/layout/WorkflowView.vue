<template>
  <div class="h-full flex flex-col overflow-hidden">

    <!-- Empty state -->
    <div v-if="threads.length === 0" class="flex-1 flex flex-col items-center justify-center gap-4 px-6 text-center">
      <div class="w-16 h-16 rounded-2xl flex items-center justify-center"
           style="background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(139,92,246,0.08));">
        <el-icon :size="28" class="text-brand/40"><Share /></el-icon>
      </div>
      <div>
        <p class="text-[13px] font-semibold text-on-surface-variant">等待 Agent 运行</p>
        <p class="text-[11px] text-on-surface-variant/60 mt-1">发送消息后将在此处实时展示执行流程</p>
      </div>
    </div>

    <!-- Thread list -->
    <div v-else class="flex-1 overflow-y-auto custom-scrollbar px-4 py-4 space-y-3">
      <TransitionGroup name="thread-enter">
        <div
          v-for="(thread, idx) in threads"
          :key="thread.threadId"
          class="workflow-thread-card rounded-2xl border overflow-hidden"
          :class="threadCardClass(thread.status)"
          :style="{ animationDelay: `${idx * 0.06}s` }"
        >
          <!-- Card header -->
          <div class="flex items-center gap-3 px-4 py-3" :class="threadHeaderClass(thread.status)">
            <!-- Agent avatar -->
            <div
              class="w-8 h-8 rounded-xl flex items-center justify-center text-white text-[12px] font-bold shrink-0"
              :style="{ background: agentGradient(thread.agentName) }"
            >
              {{ thread.agentName.charAt(0).toUpperCase() }}
            </div>

            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="text-[13px] font-semibold text-on-surface truncate">{{ thread.agentName }}</span>
                <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full shrink-0" :class="statusBadgeClass(thread.status)">
                  {{ statusLabel(thread.status) }}
                </span>
              </div>
              <div class="text-[11px] text-on-surface-variant mt-0.5 flex items-center gap-1.5">
                <span class="font-mono">{{ elapsedTime(thread) }}</span>
                <template v-if="thread.tokensOutput">
                  <span class="text-on-surface-variant/40">·</span>
                  <span>{{ thread.tokensOutput }} tok</span>
                </template>
              </div>
            </div>

            <!-- Status indicator -->
            <div class="shrink-0">
              <div v-if="thread.status === 'running'" class="w-5 h-5 rounded-full border-2 border-brand border-t-transparent animate-spin"></div>
              <el-icon v-else-if="thread.status === 'done'" class="text-success" :size="18"><CircleCheckFilled /></el-icon>
              <el-icon v-else-if="thread.status === 'error'" class="text-error" :size="18"><CircleCloseFilled /></el-icon>
            </div>
          </div>

          <!-- Block timeline -->
          <div v-if="thread.blocks.length > 0" class="px-4 py-2 space-y-1.5 border-t border-outline-variant/40">
            <div v-for="block in thread.blocks" :key="block.blockId" class="flex items-center gap-2">
              <div class="w-1.5 h-1.5 rounded-full shrink-0" :class="blockDotClass(block)"></div>
              <el-icon :size="12" class="shrink-0" :class="blockIconClass(block)">
                <component :is="blockIcon(block)" />
              </el-icon>
              <span class="text-[11px] text-on-surface-variant flex-1 truncate">{{ blockLabel(block) }}</span>
              <span v-if="block.finishedAt" class="text-[10px] text-on-surface-variant/50 font-mono shrink-0">
                {{ ((block.finishedAt - block.startedAt) / 1000).toFixed(1) }}s
              </span>
              <div v-else class="w-3 h-3 rounded-full border border-brand border-t-transparent animate-spin shrink-0"></div>
            </div>
          </div>

          <!-- Error -->
          <div v-if="thread.error" class="px-4 py-2 border-t border-error/20 bg-error-light/30">
            <p class="text-[11px] text-error">{{ thread.error }}</p>
          </div>
        </div>
      </TransitionGroup>

      <!-- Round done divider -->
      <div v-if="isRoundDone" class="flex items-center gap-2 px-2 py-1">
        <div class="flex-1 h-px bg-outline-variant"></div>
        <span class="text-[10px] text-on-surface-variant/40 font-medium shrink-0">本轮完成</span>
        <div class="flex-1 h-px bg-outline-variant"></div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { Share, CircleCheckFilled, CircleCloseFilled,
         ChatLineRound, Tools, Document, Picture, View } from '@element-plus/icons-vue'
import { useWorkflowStore, type WorkflowThread, type WorkflowBlock } from '@/stores/workflow'
import { useConversationsStore } from '@/stores/conversations'

const workflowStore = useWorkflowStore()
const conversationsStore = useConversationsStore()

const convId = computed(() => conversationsStore.currentId ?? '')
const threads = computed(() => workflowStore.getThreads(convId.value))
const isRoundDone = computed(() =>
  threads.value.length > 0 && threads.value.every(t => t.status !== 'running'),
)

// Tick every 100ms to refresh elapsed timers for running threads
const tick = ref(Date.now())
let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => { timer = setInterval(() => { tick.value = Date.now() }, 100) })
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

function elapsedTime(thread: WorkflowThread): string {
  // tick.value dependency causes reactivity update every 100ms while running
  const end = thread.finishedAt ?? tick.value
  return ((end - thread.startedAt) / 1000).toFixed(1) + 's'
}

function statusLabel(s: WorkflowThread['status']) {
  return { running: 'RUNNING', done: 'DONE', error: 'ERROR' }[s]
}

function threadCardClass(s: WorkflowThread['status']) {
  if (s === 'running') return 'border-brand/40 shadow-[0_0_20px_rgba(99,102,241,0.1)]'
  if (s === 'done')    return 'border-success/30'
  if (s === 'error')   return 'border-error/30'
  return 'border-outline-variant'
}

function threadHeaderClass(s: WorkflowThread['status']) {
  if (s === 'running') return 'bg-gradient-to-r from-brand/8 to-violet-500/5'
  if (s === 'done')    return 'bg-success-light/40'
  if (s === 'error')   return 'bg-error-light/40'
  return 'bg-surface-container-low'
}

function statusBadgeClass(s: WorkflowThread['status']) {
  if (s === 'running') return 'bg-brand/15 text-brand'
  if (s === 'done')    return 'bg-success/15 text-success'
  if (s === 'error')   return 'bg-error/15 text-error'
  return ''
}

function blockLabel(block: WorkflowBlock): string {
  if (block.type === 'tool_use') return block.toolName ?? 'tool'
  if (block.type === 'thinking') return 'thinking...'
  if (block.type === 'text')     return 'writing'
  if (block.type === 'code')     return 'code'
  if (block.type === 'image')    return 'image'
  return block.type
}

function blockIcon(block: WorkflowBlock) {
  if (block.type === 'tool_use') return Tools
  if (block.type === 'text')     return ChatLineRound
  if (block.type === 'code')     return Document
  if (block.type === 'image')    return Picture
  return View
}

function blockDotClass(block: WorkflowBlock): string {
  if (block.status === 'running') return 'bg-brand animate-pulse'
  if (block.type === 'tool_use')  return 'bg-warning'
  if (block.type === 'thinking')  return 'bg-violet-400'
  return 'bg-success'
}

function blockIconClass(block: WorkflowBlock): string {
  if (block.status === 'running') return 'text-brand'
  if (block.type === 'tool_use')  return 'text-warning'
  if (block.type === 'thinking')  return 'text-violet-400'
  return 'text-on-surface-variant/60'
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
  from { opacity: 0; transform: translateY(10px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
.workflow-thread-card {
  background: #ffffff;
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}
</style>
