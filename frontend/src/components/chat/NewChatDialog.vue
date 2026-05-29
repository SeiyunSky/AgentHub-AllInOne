<template>
  <el-dialog
    v-model="visible"
    :show-close="false"
    width="440px"
    :close-on-click-modal="true"
    :close-on-press-escape="true"
    class="new-chat-dialog"
    @opened="onOpened"
  >
    <!-- Custom Header -->
    <template #header>
      <div class="flex items-center gap-3 mb-1">
        <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-light to-brand-subtle flex items-center justify-center border border-brand/10">
          <el-icon :size="18" class="text-brand"><ChatDotRound /></el-icon>
        </div>
        <div>
          <h3 class="text-[15px] font-semibold text-on-surface leading-tight">New Chat</h3>
          <p class="text-[11px] text-on-surface-variant">Set up your conversation</p>
        </div>
      </div>
    </template>

    <div class="space-y-5">
      <!-- Chat Title -->
      <section>
        <label class="block text-[11px] font-semibold text-on-surface-variant uppercase tracking-widest mb-2">Title</label>
        <div class="title-input-wrapper group">
          <el-icon class="title-input-icon text-on-surface-variant group-focus-within:text-brand transition-colors" :size="15"><EditPen /></el-icon>
          <input
            ref="titleInputRef"
            v-model="title"
            type="text"
            placeholder="Enter chat title..."
            class="title-input"
          />
        </div>
      </section>

      <!-- Agent Selector -->
      <section>
        <label class="block text-[11px] font-semibold text-on-surface-variant uppercase tracking-widest mb-2">Invite Agents</label>

        <!-- Selected agents as chips -->
        <div v-if="selectedAgents.length > 0" class="flex flex-wrap gap-1.5 mb-2">
          <div
            v-for="agent in selectedAgents"
            :key="agent.id"
            class="agent-chip group/chip"
          >
            <div class="w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold" :class="chipAvatarClass(agent.type)">
              {{ agent.name.charAt(0) }}
            </div>
            <span class="text-[12px] font-medium">{{ agent.name }}</span>
            <button
              class="chip-remove-btn"
              @click="removeAgent(agent.id)"
            >
              <el-icon :size="8"><Close /></el-icon>
            </button>
          </div>
        </div>

        <!-- Agent dropdown picker -->
        <el-popover
          trigger="click"
          placement="bottom-start"
          :width="300"
          :show-arrow="false"
          :offset="4"
          popper-class="agent-picker-popper"
        >
          <template #reference>
            <button class="add-agent-btn">
              <el-icon :size="13"><Plus /></el-icon>
              <span class="text-[12px] font-medium">{{ selectedAgents.length > 0 ? 'Add more agents' : 'Select agents' }}</span>
            </button>
          </template>
          <div class="py-1.5">
            <!-- Search -->
            <div class="px-2 mb-1.5">
              <input
                v-model="searchQuery"
                type="text"
                placeholder="Search agents..."
                class="agent-search-input"
              />
            </div>
            <!-- Agent list -->
            <div class="max-h-48 overflow-y-auto custom-scrollbar">
              <div v-if="filteredAgents.length === 0" class="px-3 py-3 text-[12px] text-on-surface-variant text-center">
                No agents available
              </div>
              <div
                v-for="agent in filteredAgents"
                :key="agent.id"
                class="agent-option"
                @click="addAgent(agent.id)"
              >
                <div class="w-7 h-7 rounded-lg flex items-center justify-center text-[10px] font-bold shrink-0" :class="agentAvatarClass(agent.type)">
                  {{ agent.name.charAt(0) }}
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-[13px] font-medium text-on-surface truncate">{{ agent.name }}</p>
                  <p v-if="agent.description" class="text-[10px] text-on-surface-variant truncate">{{ agent.description }}</p>
                </div>
                <span class="w-1.5 h-1.5 rounded-full shrink-0" :class="typeDotClass(agent.type)"></span>
              </div>
            </div>
          </div>
        </el-popover>

        <p v-if="selectedAgents.length === 0" class="text-[11px] text-red-400 mt-1.5 pl-0.5">At least one agent is required</p>
      </section>
    </div>

    <!-- Footer -->
    <template #footer>
      <div class="flex justify-end gap-2.5 pt-2">
        <button class="btn-cancel" @click="close">Cancel</button>
        <button
          class="btn-create"
          :class="{ 'btn-create-disabled': !canCreate }"
          :disabled="!canCreate || creating"
          @click="createChat"
        >
          <el-icon v-if="creating" :size="14" class="is-loading"><Loading /></el-icon>
          {{ creating ? 'Creating...' : 'Create Chat' }}
        </button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { Close, Plus, ChatDotRound, EditPen, Loading } from '@element-plus/icons-vue'
import { useAgentsStore } from '@/stores/agents'
import { useConversationsStore } from '@/stores/conversations'
import type { Agent } from '@/types/agent'
import type { ConversationResponse } from '@/types/conversation'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'created': [conv: ConversationResponse]
}>()

const agentsStore = useAgentsStore()
const conversationsStore = useConversationsStore()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const title = ref('')
const selectedAgents = ref<Agent[]>([])
const creating = ref(false)
const searchQuery = ref('')
const titleInputRef = ref<HTMLInputElement>()

const filteredAgents = computed(() => {
  const available = agentsStore.agents.filter(
    (a) => !selectedAgents.value.some((s) => s.id === a.id)
  )
  if (!searchQuery.value) return available
  const q = searchQuery.value.toLowerCase()
  return available.filter(
    (a) => a.name.toLowerCase().includes(q) || (a.description ?? '').toLowerCase().includes(q)
  )
})

const canCreate = computed(() =>
  title.value.trim().length > 0 && selectedAgents.value.length > 0
)

function typeDotClass(type: string) {
  const map: Record<string, string> = {
    claude: 'bg-amber-400',
    codex: 'bg-emerald-400',
    opencode: 'bg-blue-400',
    custom: 'bg-purple-400',
  }
  return map[type] || 'bg-gray-400'
}

function chipAvatarClass(type: string) {
  const map: Record<string, string> = {
    claude: 'bg-amber-100 text-amber-600',
    codex: 'bg-emerald-100 text-emerald-600',
    opencode: 'bg-blue-100 text-blue-600',
    custom: 'bg-purple-100 text-purple-600',
  }
  return map[type] || 'bg-gray-100 text-gray-600'
}

function agentAvatarClass(type: string) {
  const map: Record<string, string> = {
    claude: 'bg-gradient-to-br from-amber-50 to-amber-100 text-amber-600',
    codex: 'bg-gradient-to-br from-emerald-50 to-emerald-100 text-emerald-600',
    opencode: 'bg-gradient-to-br from-blue-50 to-blue-100 text-blue-600',
    custom: 'bg-gradient-to-br from-purple-50 to-purple-100 text-purple-600',
  }
  return map[type] || 'bg-gradient-to-br from-gray-50 to-gray-100 text-gray-600'
}

function addAgent(id: string) {
  const agent = agentsStore.agents.find((a) => a.id === id)
  if (agent && !selectedAgents.value.some((a) => a.id === id)) {
    selectedAgents.value.push(agent)
  }
  searchQuery.value = ''
}

function removeAgent(id: string) {
  selectedAgents.value = selectedAgents.value.filter((a) => a.id !== id)
}

function close() {
  visible.value = false
}

function onOpened() {
  nextTick(() => {
    titleInputRef.value?.focus()
    titleInputRef.value?.select()
  })
}

async function createChat() {
  if (!canCreate.value) return
  creating.value = true
  try {
    const mode = selectedAgents.value.length > 1 ? 'group' : 'single'
    const conv = await conversationsStore.create(
      title.value.trim(),
      mode,
      selectedAgents.value.map((a) => a.id)
    )
    visible.value = false
    emit('created', conv)
  } finally {
    creating.value = false
  }
}

async function loadAgents() {
  await agentsStore.loadAgents()
}

watch(visible, async (open) => {
  if (open) {
    title.value = ''
    selectedAgents.value = []
    searchQuery.value = ''
    await loadAgents()
  }
})
</script>

<style scoped>
/* ── Title Input ── */
.title-input-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 12px;
  border: 1.5px solid var(--color-outline-variant);
  background: var(--color-surface-container-low);
  transition: all 0.2s var(--ease-out);
}
.title-input-wrapper:focus-within {
  border-color: var(--color-brand);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.08);
}
.title-input-icon {
  flex-shrink: 0;
}
.title-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--color-on-surface);
  font-family: inherit;
}
.title-input::placeholder {
  color: var(--color-on-surface-variant);
  opacity: 0.6;
}

/* ── Agent Chip ── */
.agent-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 6px 4px 8px;
  border-radius: 20px;
  background: var(--color-brand-light);
  border: 1px solid rgba(59, 130, 246, 0.12);
  color: var(--color-brand-dark);
  transition: all 0.15s ease;
}
.agent-chip:hover {
  background: rgba(59, 130, 246, 0.12);
}
.chip-remove-btn {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--color-brand);
  cursor: pointer;
  transition: all 0.15s ease;
}
.chip-remove-btn:hover {
  background: rgba(59, 130, 246, 0.2);
}

/* ── Add Agent Button ── */
.add-agent-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 10px;
  border: 1.5px dashed var(--color-outline-variant);
  background: transparent;
  color: var(--color-on-surface-variant);
  cursor: pointer;
  transition: all 0.2s var(--ease-out);
}
.add-agent-btn:hover {
  border-color: var(--color-brand);
  color: var(--color-brand);
  background: var(--color-brand-light);
}

/* ── Footer Buttons ── */
.btn-cancel {
  padding: 7px 18px;
  border-radius: 10px;
  border: 1px solid var(--color-outline-variant);
  background: transparent;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-on-surface-variant);
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-cancel:hover {
  background: var(--color-surface-container);
  color: var(--color-on-surface);
}

.btn-create {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 22px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, var(--color-brand) 0%, var(--color-brand-dark) 100%);
  font-size: 13px;
  font-weight: 500;
  color: #fff;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25);
  transition: all 0.2s var(--ease-out);
}
.btn-create:hover {
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.35);
  transform: translateY(-1px);
}
.btn-create-disabled {
  opacity: 0.45;
  cursor: not-allowed;
  box-shadow: none;
}
.btn-create-disabled:hover {
  transform: none;
  box-shadow: none;
}
</style>

<style>
/* ── Dialog Override (unscoped) ── */
.new-chat-dialog .el-dialog__header {
  padding: 20px 24px 0;
  margin-right: 0;
  border-bottom: none;
}
.new-chat-dialog .el-dialog__body {
  padding: 20px 24px;
}
.new-chat-dialog .el-dialog__footer {
  padding: 0 24px 20px;
  border-top: none;
}
.new-chat-dialog .el-dialog {
  border-radius: 20px;
  box-shadow: var(--shadow-float), 0 0 0 1px rgba(0,0,0,0.03);
  overflow: hidden;
}

/* ── Agent Picker Popover ── */
.agent-picker-popper {
  border-radius: 14px !important;
  border: 1px solid var(--color-outline-variant);
  box-shadow: var(--shadow-float) !important;
  padding: 0 !important;
}
.agent-search-input {
  width: 100%;
  padding: 6px 10px;
  border-radius: 8px;
  border: 1.5px solid var(--color-outline-variant);
  background: var(--color-surface-container-low);
  font-size: 12px;
  outline: none;
  color: var(--color-on-surface);
  transition: all 0.15s ease;
  box-sizing: border-box;
}
.agent-search-input:focus {
  border-color: var(--color-brand);
  background: #fff;
}
.agent-search-input::placeholder {
  color: var(--color-on-surface-variant);
  opacity: 0.6;
}

/* ── Agent Option ── */
.agent-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  margin: 0 4px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s ease;
}
.agent-option:hover {
  background: var(--color-brand-light);
}
</style>
