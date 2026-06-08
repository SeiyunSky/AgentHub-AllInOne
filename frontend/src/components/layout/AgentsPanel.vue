<template>
  <PanelContainer :title="t('agentsPanel.title')" :icon="User" variant="brand">
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
        v-if="!agentsStore.isLoading && filteredAgents.length === 0 && agentsStore.agents.length === 0"
        class="flex flex-col items-center justify-center h-full min-h-[400px] fade-in-up"
      >
        <div class="w-20 h-20 rounded-3xl bg-gradient-to-br from-brand-light to-brand-subtle flex items-center justify-center mb-5 shadow-soft">
          <el-icon :size="36" class="text-brand"><User /></el-icon>
        </div>
        <h3 class="text-[16px] font-semibold text-on-surface mb-1.5">{{ t('agentsPanel.emptyTitle') }}</h3>
        <p class="text-[13px] text-on-surface-variant mb-5 text-center max-w-[260px]">
          {{ t('agentsPanel.emptyDesc') }}
        </p>
        <button class="btn-create" @click="router.push({ name: 'agent-create' })">
          <el-icon :size="14"><Plus /></el-icon>
          {{ t('agentsPanel.createAgent') }}
        </button>
      </div>

      <!-- No results (has agents but filtered to none) -->
      <div
        v-else-if="!agentsStore.isLoading && filteredAgents.length === 0 && agentsStore.agents.length > 0"
        class="flex flex-col items-center justify-center h-64 text-on-surface-variant fade-in-up"
      >
        <el-icon :size="32" class="opacity-30 mb-3"><Search /></el-icon>
        <p class="text-[13px]">{{ t('agentsPanel.noMatch') }}</p>
      </div>

      <!-- Loading skeleton -->
      <div v-else-if="agentsStore.isLoading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
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
          class="premium-card overflow-hidden cursor-pointer hover:-translate-y-0.5"
          @click="router.push({ name: 'agent-edit', params: { agentId: agent.id } })"
        >
          <!-- Type accent strip -->
          <div class="h-1 bg-gradient-to-r" :class="typeAccentClass(agent.type)"></div>

          <div class="p-5">
            <div class="flex items-start gap-3 mb-3">
              <div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 overflow-hidden border border-outline-variant bg-surface-container">
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
                :title="agent.isActive ? t('agentsPanel.tooltipActive') : t('agentsPanel.tooltipInactive')"
              ></div>
            </div>

            <p class="text-[12px] text-on-surface-variant line-clamp-2 mb-3 min-h-[32px]">
              {{ agent.description || t('agentsPanel.noDescription') }}
            </p>

            <AgentCapabilityTags :capabilities="agent.capabilities" />

            <div class="mt-3 flex items-center">
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
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- AI Builder dialog -->
    <AgentBuilderDialog
      v-model="showBuilderDialog"
      @confirmed="onAgentBuilt"
    />
  </PanelContainer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { User, Plus, Search } from '@element-plus/icons-vue'
import { useAgentsStore } from '@/stores/agents'
import PanelContainer from '@/components/layout/PanelContainer.vue'
import AgentCapabilityTags from '@/components/agents/AgentCapabilityTags.vue'
import AgentBuilderDialog from '@/components/agents/AgentBuilderDialog.vue'
import { getAgentTypeIcon } from '@/utils/agentIcons'

const { t } = useI18n()
const router = useRouter()
const agentsStore = useAgentsStore()

const showBuilderDialog = ref(false)
const activeFilter = ref('all')

const filterOptions = computed(() => [
  { label: t('agentsPanel.filterAll'), value: 'all' },
  { label: t('agentsPanel.filterActive'), value: 'active' },
  { label: t('agentsPanel.filterClaude'), value: 'claude' },
  { label: t('agentsPanel.filterCodex'), value: 'codex' },
  { label: t('agentsPanel.filterCustom'), value: 'custom' },
])

const filteredAgents = computed(() => {
  const agents = agentsStore.agents
  if (activeFilter.value === 'active') return agents.filter(a => a.isActive)
  if (activeFilter.value !== 'all') return agents.filter(a => a.type === activeFilter.value)
  return agents
})

onMounted(async () => {
  if (agentsStore.agents.length === 0) {
    await agentsStore.loadAgents()
  }
})

function typeAccentClass(type: string) {
  const map: Record<string, string> = {
    claude:    'from-amber-200 to-amber-400',
    codex:     'from-emerald-200 to-emerald-400',
    opencode:  'from-blue-200 to-blue-400',
    custom:    'from-purple-200 to-purple-400',
  }
  return map[type] || 'from-slate-200 to-slate-400'
}


function hideImg(e: Event) {
  ;(e.target as HTMLImageElement).style.display = 'none'
}

function onAgentBuilt(draft: any) {
  agentsStore.initialDraft = draft
  router.push({ name: 'agent-create' })
}
</script>
