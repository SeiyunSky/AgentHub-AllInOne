<template>
  <el-dialog
    v-model="visible"
    :show-close="false"
    width="520px"
    :close-on-click-modal="true"
    :close-on-press-escape="true"
    class="conv-settings-dialog"
  >
    <!-- Header -->
    <template #header>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-light to-brand-subtle flex items-center justify-center border border-brand/10">
            <el-icon :size="18" class="text-brand"><Setting /></el-icon>
          </div>
          <div>
            <h3 class="text-[15px] font-semibold text-on-surface leading-tight">会话设置</h3>
            <p class="text-[11px] text-on-surface-variant truncate max-w-[300px]">{{ conversationTitle }}</p>
          </div>
        </div>
        <button
          class="w-7 h-7 rounded-full flex items-center justify-center hover:bg-surface-container transition shrink-0"
          @click="close"
        >
          <el-icon :size="14"><Close /></el-icon>
        </button>
      </div>
    </template>

    <!-- Body 滚动区(限高,内容多时可滚) -->
    <div class="space-y-5 max-h-[65vh] overflow-y-auto custom-scrollbar pr-1">

      <!-- ── 群成员管理 ── -->
      <section>
        <div class="flex items-center justify-between mb-3">
          <h4 class="text-[11px] font-semibold text-on-surface-variant uppercase tracking-widest">群成员 ({{ members.length }})</h4>
          <button
            class="text-[11px] font-medium text-brand hover:underline inline-flex items-center gap-1"
            @click="showAddPicker = !showAddPicker"
          >
            <el-icon :size="11"><Plus /></el-icon>
            {{ showAddPicker ? '收起' : '添加成员' }}
          </button>
        </div>

        <!-- 添加 Agent 选择器 -->
        <div v-if="showAddPicker" class="mb-3 p-3 rounded-xl bg-surface-container/60 border border-outline-variant space-y-1">
          <div v-if="addableAgents.length === 0" class="text-[12px] text-on-surface-variant text-center py-3">
            没有可添加的 Agent
          </div>
          <div
            v-for="agent in addableAgents"
            :key="agent.id"
            class="flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-white cursor-pointer transition"
            @click="onAdd(agent.id)"
          >
            <div class="w-7 h-7 rounded-lg bg-brand-light text-brand text-[11px] font-bold flex items-center justify-center shrink-0">
              {{ agent.name.charAt(0) }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-[12px] font-medium text-on-surface truncate">{{ agent.name }}</div>
              <div class="text-[10px] text-on-surface-variant truncate">{{ agent.description ?? '—' }}</div>
            </div>
            <el-icon :size="12" class="text-brand"><Plus /></el-icon>
          </div>
        </div>

        <!-- 现有成员列表 -->
        <div class="space-y-2">
          <div
            v-for="member in members"
            :key="member.id"
            class="flex items-center gap-3 p-2.5 rounded-xl bg-white border"
            :class="member.id === 'orchestrator' ? 'border-brand/30 bg-brand-light/30' : 'border-outline-variant'"
          >
            <div
              class="w-9 h-9 rounded-lg text-[12px] font-bold flex items-center justify-center shrink-0"
              :class="member.id === 'orchestrator' ? 'bg-brand text-white' : 'bg-brand-light text-brand'"
            >
              {{ member.name.charAt(0) }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="text-[13px] font-medium text-on-surface truncate">{{ member.name }}</span>
                <span
                  v-if="member.id === 'orchestrator'"
                  class="text-[9px] font-semibold px-1.5 py-0.5 rounded uppercase bg-brand text-white"
                >系统 · 群主</span>
                <span
                  v-else
                  class="text-[9px] font-semibold px-1.5 py-0.5 rounded uppercase"
                  :class="typeBadgeClass(member.type)"
                >{{ member.type }}</span>
              </div>
              <div class="text-[10px] text-on-surface-variant mt-0.5 tabular-nums">
                <span class="text-brand font-medium">{{ formatNum(tokensFor(member.id).input) }}</span> in /
                <span class="text-success font-medium">{{ formatNum(tokensFor(member.id).output) }}</span> out ·
                {{ tokensFor(member.id).count }} 条消息
              </div>
            </div>
            <button
              v-if="canRemove(member)"
              class="w-7 h-7 rounded-md flex items-center justify-center text-on-surface-variant hover:bg-error-light hover:text-error transition shrink-0"
              :title="`从会话移除 ${member.name}`"
              @click="onRemove(member.id)"
            >
              <el-icon :size="13"><Delete /></el-icon>
            </button>
          </div>
        </div>
      </section>

      <!-- ── Token 用量 ── -->
      <section>
        <h4 class="text-[11px] font-semibold text-on-surface-variant uppercase tracking-widest mb-3">Token 用量</h4>

        <div v-if="loadingTokens" class="text-[12px] text-on-surface-variant text-center py-6">
          加载中...
        </div>

        <template v-else>
          <!-- 总用量大数字 -->
          <div class="p-4 rounded-xl bg-gradient-to-br from-brand-light to-brand-subtle border border-brand/10 mb-3">
            <div class="flex items-baseline gap-2">
              <span class="text-[11px] font-semibold text-brand uppercase tracking-wider">总 Token 用量</span>
            </div>
            <div class="text-[28px] font-bold text-brand-dark mt-1 tabular-nums leading-none">
              {{ formatNum(totalTokens) }}
            </div>
            <div class="text-[10px] text-on-surface-variant mt-2 tabular-nums">
              <span class="text-brand font-medium">{{ formatNum(tokenUsage?.total.tokens_input ?? 0) }}</span> 输入
              <span class="mx-1.5 opacity-40">·</span>
              <span class="text-success font-medium">{{ formatNum(tokenUsage?.total.tokens_output ?? 0) }}</span> 输出
            </div>
          </div>

          <!-- 按 Agent 拆分 -->
          <div v-if="tokenUsage && tokenUsage.by_agent.length > 0" class="rounded-xl border border-outline-variant overflow-hidden">
            <div
              v-for="(row, idx) in tokenUsage.by_agent"
              :key="row.agent_id"
              class="flex items-center gap-2 px-3 py-2.5 text-[11px] tabular-nums"
              :class="idx > 0 ? 'border-t border-outline-variant' : ''"
            >
              <div class="flex-1 min-w-0">
                <div class="text-[12px] font-medium text-on-surface truncate">{{ row.agent_name }}</div>
                <div class="text-[10px] text-on-surface-variant mt-0.5">
                  <span>{{ formatNum(row.tokens_input) }} 输入</span>
                  <span class="mx-1 opacity-40">·</span>
                  <span>{{ formatNum(row.tokens_output) }} 输出</span>
                  <span class="mx-1 opacity-40">·</span>
                  <span>{{ row.messages_count }} 条</span>
                </div>
              </div>
              <span class="text-brand-dark font-bold tabular-nums">
                {{ formatNum(row.tokens_input + row.tokens_output) }}
              </span>
            </div>
          </div>
          <div v-else class="text-[11px] text-on-surface-variant text-center py-4">
            本会话还没有 token 消耗
          </div>
        </template>
      </section>
    </div>

    <!-- Footer -->
    <template #footer>
      <div class="flex justify-between items-center pt-2">
        <button
          class="text-[11px] text-on-surface-variant hover:text-brand inline-flex items-center gap-1"
          @click="loadTokenUsage"
        >
          <el-icon :size="11"><Refresh /></el-icon>
          刷新用量
        </button>
        <button class="btn-close" @click="close">关闭</button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Close, Plus, Delete, Setting, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useConversationsStore } from '@/stores/conversations'
import { useAgentsStore } from '@/stores/agents'
import { conversationsApi, type ConversationTokenUsage } from '@/api/conversations'
import type { AgentMember } from '@/types/conversation'

const props = defineProps<{
  modelValue: boolean
  conversationId: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const conversationsStore = useConversationsStore()
const agentsStore = useAgentsStore()

const conversationTitle = computed(() => {
  const conv = conversationsStore.conversations.find(c => c.id === props.conversationId)
  return conv?.title ?? '未命名会话'
})

const members = computed<AgentMember[]>(() => {
  const conv = conversationsStore.currentConversation
  if (!conv || conv.id !== props.conversationId) return []
  // 主 Agent (orchestrator) 显示出来让用户知道在场,但 canRemove 会拦掉删除按钮
  // 同时把它排到列表第一位(系统级成员,视觉上区分)
  const all = conv.agents ?? []
  const orchestrator = all.find(a => a.id === 'orchestrator')
  const others = all.filter(a => a.id !== 'orchestrator')
  return orchestrator ? [orchestrator, ...others] : others
})

const showAddPicker = ref(false)
const addableAgents = computed(() => {
  const memberIds = new Set([
    ...members.value.map(m => m.id),
    'orchestrator',  // 主 Agent 不能由用户手动加(避免重复)
  ])
  return agentsStore.agents.filter(a => !memberIds.has(a.id))
})

const tokenUsage = ref<ConversationTokenUsage | null>(null)
const loadingTokens = ref(false)

const totalTokens = computed(() => {
  if (!tokenUsage.value) return 0
  return (tokenUsage.value.total.tokens_input ?? 0) + (tokenUsage.value.total.tokens_output ?? 0)
})

async function loadTokenUsage() {
  if (!props.conversationId) return
  loadingTokens.value = true
  try {
    tokenUsage.value = await conversationsApi.tokenUsage(props.conversationId)
  } catch (err) {
    console.error('Failed to load token usage', err)
    tokenUsage.value = null
  } finally {
    loadingTokens.value = false
  }
}

watch(
  () => [visible.value, props.conversationId] as const,
  ([open]) => {
    if (open) {
      loadTokenUsage()
      showAddPicker.value = false
      agentsStore.loadAgents().catch(() => {})
    }
  },
  { immediate: false },
)

function tokensFor(agentId: string) {
  const row = tokenUsage.value?.by_agent.find(r => r.agent_id === agentId)
  return {
    input: row?.tokens_input ?? 0,
    output: row?.tokens_output ?? 0,
    count: row?.messages_count ?? 0,
  }
}

function canRemove(member: AgentMember): boolean {
  // 单聊只有 1 个成员,不允许删空;orchestrator 是群聊主 Agent,也不能踢
  if (member.id === 'orchestrator') return false
  return members.value.length > 1
}

function typeBadgeClass(type: string): string {
  switch (type) {
    case 'claude': return 'bg-amber-100 text-amber-700'
    case 'codex': return 'bg-emerald-100 text-emerald-700'
    case 'opencode': return 'bg-blue-100 text-blue-700'
    case 'custom': return 'bg-purple-100 text-purple-700'
    default: return 'bg-surface-container text-on-surface-variant'
  }
}

function formatNum(n: number): string {
  if (n < 1000) return String(n)
  if (n < 1_000_000) return (n / 1000).toFixed(1) + 'k'
  return (n / 1_000_000).toFixed(1) + 'M'
}

async function refreshConversation() {
  // 重新拉一遍当前会话(把 members 同步到 currentConversation)
  if (conversationsStore.currentId === props.conversationId) {
    try {
      const fresh = await conversationsApi.get(props.conversationId)
      conversationsStore.currentConversation = fresh
    } catch {
      // ignore
    }
  }
}

async function onAdd(agentId: string) {
  try {
    await conversationsApi.addAgent(props.conversationId, agentId)
    await refreshConversation()
    showAddPicker.value = false
    ElMessage({ message: '已添加', type: 'success', duration: 1500, plain: true })
  } catch (err) {
    console.error(err)
    ElMessage({ message: '添加失败,请重试', type: 'error', duration: 2000, plain: true })
  }
}

async function onRemove(agentId: string) {
  try {
    await conversationsApi.removeAgent(props.conversationId, agentId)
    await refreshConversation()
    ElMessage({ message: '已移除', type: 'success', duration: 1500, plain: true })
  } catch (err) {
    console.error(err)
    ElMessage({ message: '移除失败,请重试', type: 'error', duration: 2000, plain: true })
  }
}

function close() {
  visible.value = false
}
</script>

<style scoped>
.btn-close {
  padding: 6px 18px;
  border-radius: 10px;
  border: 1px solid var(--color-outline-variant);
  background: transparent;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-on-surface-variant);
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-close:hover {
  background: var(--color-surface-container);
  color: var(--color-on-surface);
}
</style>

<style>
/* ── Dialog Override (unscoped) ── */
.conv-settings-dialog .el-dialog {
  border-radius: 20px;
  box-shadow: var(--shadow-float), 0 0 0 1px rgba(0,0,0,0.03);
  overflow: hidden;
}
.conv-settings-dialog .el-dialog__header {
  padding: 20px 24px 12px;
  margin-right: 0;
  border-bottom: 1px solid var(--color-outline-variant);
}
.conv-settings-dialog .el-dialog__body {
  padding: 18px 24px;
}
.conv-settings-dialog .el-dialog__footer {
  padding: 12px 24px 18px;
  border-top: 1px solid var(--color-outline-variant);
}
</style>
