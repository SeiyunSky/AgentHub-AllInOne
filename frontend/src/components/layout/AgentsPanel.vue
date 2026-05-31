<template>
  <PanelContainer title="Agents" :icon="User" variant="brand">
    <template #headerActions>
      <div class="flex items-center gap-2">
        <button
          class="h-8 px-4 rounded-lg flex items-center gap-2 text-[13px] font-medium border border-outline-variant text-on-surface-variant hover:bg-surface-container transition-colors cursor-pointer"
          @click="showBuilderDialog = true"
        >
          <el-icon :size="14"><MagicStick /></el-icon>
          Build with AI
        </button>
        <button
          class="h-8 px-4 rounded-lg flex items-center gap-2 bg-brand text-white text-[13px] font-medium shadow-sm hover:bg-brand-dark transition-colors cursor-pointer"
          @click="openCreate"
        >
          <el-icon :size="14"><Plus /></el-icon>
          New Agent
        </button>
      </div>
    </template>

    <div class="p-6 overflow-y-auto h-full custom-scrollbar">
      <!-- Empty state -->
      <div
        v-if="!isLoading && agents.length === 0"
        class="flex flex-col items-center justify-center h-64 text-on-surface-variant gap-3"
      >
        <el-icon :size="40" class="opacity-30"><User /></el-icon>
        <p class="text-[14px]">No agents yet</p>
        <button
          class="px-4 py-2 rounded-lg bg-brand text-white text-[13px] font-medium hover:bg-brand-dark transition-colors cursor-pointer"
          @click="openCreate"
        >
          Create your first agent
        </button>
      </div>

      <!-- Loading skeleton -->
      <div v-else-if="isLoading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="n in 6" :key="n" class="rounded-2xl border border-outline-variant p-5 space-y-3">
          <el-skeleton animated>
            <template #template>
              <div class="flex items-center gap-3">
                <el-skeleton-item variant="circle" style="width: 40px; height: 40px;" />
                <div class="flex-1 space-y-1.5">
                  <el-skeleton-item variant="text" style="width: 60%;" />
                  <el-skeleton-item variant="text" style="width: 40%;" />
                </div>
              </div>
              <el-skeleton-item variant="text" style="width: 100%; margin-top: 12px;" />
              <el-skeleton-item variant="text" style="width: 80%;" />
            </template>
          </el-skeleton>
        </div>
      </div>

      <!-- Agent cards grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="agent in agents"
          :key="agent.id"
          class="group rounded-2xl border border-outline-variant bg-white p-5 hover:border-brand hover:shadow-card hover:-translate-y-0.5 transition-all duration-200 cursor-pointer"
          @click="openEdit(agent)"
        >
          <div class="flex items-start gap-3 mb-3">
            <div
              class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              :class="agent.isActive ? 'bg-gradient-to-br from-brand-light to-brand-subtle border border-brand/20' : 'bg-surface-container border border-outline-variant'"
            >
              <el-icon :class="agent.isActive ? 'text-brand' : 'text-on-surface-variant'" :size="18"><User /></el-icon>
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-[14px] font-semibold text-on-surface truncate">{{ agent.name }}</p>
              <p class="text-[11px] text-on-surface-variant truncate capitalize">{{ agent.type }}</p>
            </div>
            <span
              class="w-2 h-2 rounded-full shrink-0 mt-1.5"
              :class="agent.isActive ? 'bg-emerald-400' : 'bg-outline'"
              :title="agent.isActive ? 'Active' : 'Inactive'"
            ></span>
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
                class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-surface-container text-on-surface-variant"
              >
                {{ tag }}
              </span>
              <span
                v-if="agent.tags.length > 2"
                class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-surface-container text-on-surface-variant"
              >
                +{{ agent.tags.length - 2 }}
              </span>
            </div>
            <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                class="w-7 h-7 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container transition-colors"
                title="Edit"
                @click.stop="openEdit(agent)"
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

    <!-- Create / Edit drawer -->
    <AgentConfigForm
      v-model="showConfigForm"
      :agent-id="editingAgentId"
      :initial-draft="initialDraft"
      @saved="onAgentSaved"
    />

    <!-- AI Builder dialog -->
    <AgentBuilderDialog
      v-model="showBuilderDialog"
      @confirmed="onBuilderConfirmed"
    />
  </PanelContainer>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { User, Plus, MagicStick, EditPen, Delete } from '@element-plus/icons-vue'
import { useAgentsStore } from '@/stores/agents'
import { agentsApi } from '@/api/agents'
import type { Agent, AgentDraft } from '@/types/agent'
import PanelContainer from '@/components/layout/PanelContainer.vue'
import AgentCapabilityTags from '@/components/agents/AgentCapabilityTags.vue'
import AgentConfigForm from '@/components/agents/AgentConfigForm.vue'
import AgentBuilderDialog from '@/components/agents/AgentBuilderDialog.vue'

const router = useRouter()
const agentsStore = useAgentsStore()

const agents = agentsStore.agents
const isLoading = ref(false)

const showConfigForm = ref(false)
const editingAgentId = ref<string | undefined>(undefined)
const initialDraft = ref<Partial<AgentDraft> | undefined>(undefined)

const showBuilderDialog = ref(false)

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

function openCreate() {
  editingAgentId.value = undefined
  initialDraft.value = undefined
  showConfigForm.value = true
}

function openEdit(agent: Agent) {
  editingAgentId.value = agent.id
  initialDraft.value = undefined
  showConfigForm.value = true
}

function onAgentSaved(saved: Agent) {
  const idx = agentsStore.agents.findIndex(a => a.id === saved.id)
  if (idx >= 0) {
    agentsStore.agents.splice(idx, 1, saved)
  } else {
    agentsStore.agents.unshift(saved)
  }
}

function onBuilderConfirmed(draft: AgentDraft) {
  editingAgentId.value = undefined
  initialDraft.value = draft
  showConfigForm.value = true
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