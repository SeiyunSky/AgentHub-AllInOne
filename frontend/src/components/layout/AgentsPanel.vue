<template>
  <PanelContainer title="Agents" :icon="User" variant="brand">
    <!-- Content area -->
    <div class="p-6 overflow-y-auto h-full custom-scrollbar">

      <!-- Filter Bar -->
      <div class="flex items-center gap-1.5 flex-wrap mb-5">
        <button
          v-for="f in filterOptions"
          :key="f.value"
          class="px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all cursor-pointer whitespace-nowrap"
          :class="activeFilter === f.value
            ? 'bg-brand text-white shadow-soft'
            : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'"
          @click="activeFilter = f.value"
        >
          {{ f.label }}
        </button>
      </div>

      <!-- Empty state -->
      <div
        v-if="!isLoading && filteredAgents.length === 0 && agents.length === 0"
        class="flex flex-col items-center justify-center h-full min-h-[400px] fade-in-up"
      >
        <div class="w-20 h-20 rounded-3xl bg-gradient-to-br from-brand-light to-brand-subtle flex items-center justify-center mb-5 shadow-soft">
          <el-icon :size="36" class="text-brand"><User /></el-icon>
        </div>
        <h3 class="text-[16px] font-semibold text-on-surface mb-1.5">No agents yet</h3>
        <p class="text-[13px] text-on-surface-variant mb-5 text-center max-w-[260px]">
          Create your first AI agent to get started. Each agent can have unique skills and behaviors.
        </p>
        <button class="btn-create" @click="router.push({ name: 'agent-create' })">
          <el-icon :size="14"><Plus /></el-icon>
          Create Agent
        </button>
      </div>

      <!-- No results (has agents but filtered to none) -->
      <div
        v-else-if="!isLoading && filteredAgents.length === 0 && agents.length > 0"
        class="flex flex-col items-center justify-center h-64 text-on-surface-variant fade-in-up"
      >
        <el-icon :size="32" class="opacity-30 mb-3"><Search /></el-icon>
        <p class="text-[13px]">No agents match your search</p>
      </div>

      <!-- Loading skeleton -->
      <div v-else-if="isLoading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
        <div v-for="n in 6" :key="n" class="premium-card p-5 space-y-4">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-surface-container-high shimmer"></div>
            <div class="flex-1 space-y-2">
              <div class="h-3.5 rounded-md bg-surface-container-high shimmer w-3/5"></div>
              <div class="h-2.5 rounded-md bg-surface-container-high shimmer w-2/5"></div>
            </div>
          </div>
          <div class="space-y-2">
            <div class="h-3 rounded-md bg-surface-container-high shimmer w-full"></div>
            <div class="h-3 rounded-md bg-surface-container-high shimmer w-4/5"></div>
          </div>
          <div class="flex gap-2 pt-3 border-t border-outline-variant">
            <div class="h-5 w-14 rounded-full bg-surface-container-high shimmer"></div>
            <div class="h-5 w-14 rounded-full bg-surface-container-high shimmer"></div>
          </div>
        </div>
      </div>

      <!-- Agent cards grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
        <div
          v-for="agent in filteredAgents"
          :key="agent.id"
          class="premium-card group overflow-hidden cursor-pointer hover:-translate-y-0.5"
          @click="router.push({ name: 'agent-edit', params: { agentId: agent.id } })"
        >
          <!-- Type accent strip -->
          <div class="h-1" :class="typeAccentClass(agent.type)"></div>

          <div class="p-5">
            <div class="flex items-start gap-3 mb-3">
              <div
                class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border overflow-hidden"
                :class="agentAvatarClass(agent.type)"
              >
                <img v-if="agent.avatar" :src="agent.avatar" :alt="agent.name" class="w-full h-full object-cover" />
                <img v-else :src="getAgentTypeIcon(agent.type)" :alt="agent.type" class="w-6 h-6 object-contain" @error="hideImg" />
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-[14px] font-semibold text-on-surface truncate">{{ agent.name }}</p>
                <p class="text-[11px] text-on-surface-variant truncate capitalize">{{ agent.type }}</p>
              </div>
              <div
                class="shrink-0 mt-1.5"
                :class="agent.isActive ? 'status-dot-active agent-pulse' : 'status-dot-inactive'"
                :title="agent.isActive ? 'Active' : 'Inactive'"
              ></div>
            </div>

            <p class="text-[12px] text-on-surface-variant line-clamp-2 mb-3 min-h-[32px]">
              {{ agent.description || 'No description' }}
            </p>

            <AgentCapabilityTags :capabilities="agent.capabilities" />

            <div class="mt-3 pt-3 border-t border-outline-variant flex items-center justify-between">
              <div class="flex gap-1 flex-wrap">
                <span
                  v-for="tag in agent.tags.slice(0, 2)"
                  :key="tag"
                  class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-surface-container-low text-on-surface-variant"
                >
                  {{ tag }}
                </span>
                <span
                  v-if="agent.tags.length > 2"
                  class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-surface-container-low text-on-surface-variant"
                >
                  +{{ agent.tags.length - 2 }}
                </span>
              </div>
              <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  class="w-7 h-7 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container transition-colors"
                  title="Edit"
                  @click.stop="router.push({ name: 'agent-edit', params: { agentId: agent.id } })"
                >
                  <el-icon :size="14"><EditPen /></el-icon>
                </button>
                <button
                  class="w-7 h-7 rounded-lg flex items-center justify-center text-red-400 hover:bg-red-50 transition-colors"
                  title="Delete"
                  @click.stop="confirmDelete(agent)"
                >
                  <el-icon :size="14"><Delete /></el-icon>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- AI Builder dialog -->
    <AgentBuilderDialog
      v-model="showBuilderDialog"
      @confirmed="onBuilderConfirmed"
    />
  </PanelContainer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { User, EditPen, Delete, Plus, Search } from '@element-plus/icons-vue'
import { useAgentsStore } from '@/stores/agents'
import { agentsApi } from '@/api/agents'
import type { Agent } from '@/types/agent'
import PanelContainer from '@/components/layout/PanelContainer.vue'
import AgentCapabilityTags from '@/components/agents/AgentCapabilityTags.vue'
import AgentBuilderDialog from '@/components/agents/AgentBuilderDialog.vue'
import { getAgentTypeIcon } from '@/utils/agentIcons'

const router = useRouter()
const agentsStore = useAgentsStore()

const agents = agentsStore.agents
const isLoading = ref(false)
const showBuilderDialog = ref(false)
const activeFilter = ref('all')

const filterOptions = [
  { label: 'All', value: 'all' },
  { label: 'Active', value: 'active' },
  { label: 'Claude', value: 'claude' },
  { label: 'Codex', value: 'codex' },
  { label: 'Custom', value: 'custom' },
]

const filteredAgents = computed(() => {
  if (activeFilter.value === 'active') {
    return agents.filter(a => a.isActive)
  } else if (activeFilter.value !== 'all') {
    return agents.filter(a => a.type === activeFilter.value)
  }
  return agents
})

onMounted(async () => {
  if (agents.length === 0) {
    isLoading.value = true
    try {
      const data = await agentsApi.list()
      agentsStore.agents = data.map(rawToAgent)
    } finally {
      isLoading.value = false
    }
  }
})

function rawToAgent(raw: any): Agent {
  return {
    id: raw.id,
    name: raw.name,
    description: raw.description,
    type: raw.type,
    avatar: raw.avatar,
    systemPrompt: raw.system_prompt,
    capabilities: {
      supportsCode: raw.capabilities.supports_code,
      supportsDiff: raw.capabilities.supports_diff,
      supportsApproval: raw.capabilities.supports_approval,
      supportsImage: raw.capabilities.supports_image,
    },
    tags: raw.tags ?? [],
    isPublic: raw.is_public,
    isActive: raw.is_active,
    createdAt: new Date(raw.created_at),
    updatedAt: new Date(raw.updated_at),
  }
}

function typeAccentClass(type: string) {
  const map: Record<string, string> = {
    claude: 'bg-gradient-to-r from-amber-300 to-amber-400',
    codex: 'bg-gradient-to-r from-emerald-400 to-emerald-500',
    opencode: 'bg-gradient-to-r from-blue-400 to-blue-500',
    custom: 'bg-gradient-to-r from-purple-400 to-purple-500',
  }
  return map[type] || 'bg-gradient-to-r from-slate-300 to-slate-400'
}

function agentAvatarClass(type: string) {
  const map: Record<string, string> = {
    claude: 'bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200/50',
    codex: 'bg-gradient-to-br from-emerald-50 to-emerald-100 border-emerald-200/50',
    opencode: 'bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200/50',
    custom: 'bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200/50',
  }
  return map[type] || 'bg-gradient-to-br from-slate-50 to-slate-100 border-slate-200/50'
}

function hideImg(e: Event) {
  ;(e.target as HTMLImageElement).style.display = 'none'
}

function onBuilderConfirmed(draft: any) {
  agentsStore.initialDraft = draft
  router.push({ name: 'agent-create' })
}

async function confirmDelete(agent: Agent) {
  try {
    await ElMessageBox.confirm(
      `Delete agent "${agent.name}"? This cannot be undone.`,
      'Delete Agent',
      { confirmButtonText: 'Delete', cancelButtonText: 'Cancel', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await agentsApi.deactivate(agent.id)
    const idx = agentsStore.agents.findIndex(a => a.id === agent.id)
    if (idx >= 0) agentsStore.agents.splice(idx, 1)
    ElMessage.success('Agent deleted')
  } catch {
    ElMessage.error('Failed to delete agent')
  }
}
</script>
