<template>
  <Splitpanes class="splitpanes-theme" @resized="onPaneResized">
    <Pane :size="chatPaneSize" :min-size="35">
      <PanelContainer
        :title="isEditMode ? 'Edit Agent' : 'Create Agent'"
        :icon="User"
        variant="brand"
      >
        <template #headerActions>
          <div class="flex items-center gap-2">
            <button
              v-if="isEditMode"
              class="h-8 px-4 rounded-lg text-[13px] font-medium border border-red-200 bg-white text-red-500 hover:bg-red-50 hover:border-red-300 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isDeleting"
              @click="handleDelete"
            >
              <el-icon v-if="isDeleting" :size="14" class="is-loading mr-1.5"><Loading /></el-icon>
              Delete
            </button>
            <button
              class="h-8 px-4 rounded-lg text-[13px] font-medium border border-outline-variant bg-white text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-all cursor-pointer"
              @click="handleCancel"
            >
              Cancel
            </button>
            <button
              class="h-8 px-4 rounded-lg text-[13px] font-medium bg-gradient-to-r from-brand to-brand-dark text-white shadow-soft hover:shadow-glow hover:-translate-y-px transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
              :disabled="isSaving"
              @click="handleSave"
            >
              <el-icon v-if="isSaving" :size="14" class="is-loading mr-1.5"><Loading /></el-icon>
              {{ isEditMode ? 'Save Changes' : 'Create Agent' }}
            </button>
            <button
              class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container transition-colors cursor-pointer"
              @click="toggleChat"
            >
              <el-icon :size="16">
                <ArrowRight v-if="chatVisible" />
                <ArrowLeft v-else />
              </el-icon>
            </button>
          </div>
        </template>
        <div class="h-full overflow-y-auto">
          <!-- Loading skeleton for edit mode -->
          <div v-if="isLoading" class="p-8 space-y-5">
            <div class="flex items-center gap-4">
              <div class="w-14 h-14 rounded-2xl bg-surface-container-high shimmer"></div>
              <div class="flex-1 space-y-2">
                <div class="h-7 rounded-lg bg-surface-container-high shimmer w-2/3"></div>
                <div class="h-4 rounded-lg bg-surface-container-high shimmer w-1/3"></div>
              </div>
            </div>
            <div v-for="n in 4" :key="n" class="space-y-3">
              <div class="h-3 rounded bg-surface-container-high shimmer w-24"></div>
              <div class="h-20 rounded-xl bg-surface-container-high shimmer"></div>
            </div>
          </div>
          <AgentForm v-else :draft="localDraft" :edit-mode="isEditMode" />
        </div>
      </PanelContainer>
    </Pane>
    <Pane v-if="chatVisible" :size="100 - chatPaneSize" :min-size="25">
      <ChatPanel hide-header />
    </Pane>
  </Splitpanes>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, ArrowRight, ArrowLeft, Loading } from '@element-plus/icons-vue'
import { Splitpanes, Pane } from 'splitpanes'
import 'splitpanes/dist/splitpanes.css'
import { useAgentsStore } from '@/stores/agents'
import { agentsApi, type AgentResponse } from '@/api/agents'
import type { AgentDraft } from '@/types/agent'
import PanelContainer from '@/components/layout/PanelContainer.vue'
import AgentForm from '@/components/agents/AgentForm.vue'
import ChatPanel from '@/components/layout/ChatPanel.vue'

const route = useRoute()
const router = useRouter()
const agentsStore = useAgentsStore()

const isSaving = ref(false)
const isDeleting = ref(false)
const isLoading = ref(false)
const chatVisible = ref(true)
const chatPaneSize = ref(70)

const agentId = computed(() => route.params.agentId as string | undefined)
const isEditMode = computed(() => !!agentId.value)

const defaultDraft: AgentDraft = {
  name: '',
  description: '',
  type: 'claude',
  systemPrompt: '',
  capabilities: { supportsCode: true, supportsDiff: false, supportsApproval: false, supportsImage: false },
  tags: [],
  isPublic: false,
  isActive: true,
  skillIds: [],
}

const localDraft = ref<AgentDraft>({ ...defaultDraft })

function rawToDraft(raw: AgentResponse): AgentDraft {
  return {
    name: raw.name,
    description: raw.description,
    type: raw.type as AgentDraft['type'],
    avatar: raw.avatar,
    systemPrompt: raw.system_prompt,
    capabilities: {
      supportsCode: raw.capabilities.supports_code,
      supportsDiff: raw.capabilities.supports_diff,
      supportsApproval: raw.capabilities.supports_approval,
      supportsImage: raw.capabilities.supports_image,
    },
    tags: raw.tags,
    isPublic: raw.is_public,
    isActive: raw.is_active,
    skillIds: raw.skill_ids ?? [],
  }
}

async function loadAgentById(id: string) {
  isLoading.value = true
  try {
    localDraft.value = rawToDraft(await agentsApi.get(id))
  } catch {
    ElMessage.error('Failed to load agent')
    router.push({ name: 'agents' })
  } finally {
    isLoading.value = false
  }
}

onMounted(async () => {
  if (isEditMode.value) {
    await loadAgentById(agentId.value!)
  } else {
    localDraft.value = { ...defaultDraft, ...agentsStore.initialDraft }
    agentsStore.initialDraft = undefined
  }
})

watch(agentId, async (newId) => {
  if (newId) {
    await loadAgentById(newId)
  } else {
    localDraft.value = { ...defaultDraft }
  }
})

function handleCancel() {
  router.push({ name: 'agents' })
}

function onPaneResized(event: ({ size: number })[]) {
  if (event.length > 0) {
    chatPaneSize.value = event[0].size
  }
}

function toggleChat() {
  if (!chatVisible.value) {
    chatPaneSize.value = 70
  }
  chatVisible.value = !chatVisible.value
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm(
      `Delete agent "${localDraft.value.name}"? This cannot be undone.`,
      'Delete Agent',
      { confirmButtonText: 'Delete', cancelButtonText: 'Cancel', type: 'warning' },
    )
  } catch {
    return
  }
  isDeleting.value = true
  try {
    await agentsApi.delete(agentId.value!)
    agentsStore.removeAgent(agentId.value!)
    ElMessage.success('Agent deleted')
    router.push({ name: 'agents' })
  } catch {
    ElMessage.error('Failed to delete agent')
  } finally {
    isDeleting.value = false
  }
}

async function handleSave() {
  if (!localDraft.value.name.trim()) {
    ElMessage.warning('Agent name is required')
    return
  }
  isSaving.value = true
  try {
    const payload = {
      name: localDraft.value.name,
      description: localDraft.value.description,
      type: localDraft.value.type,
      avatar: localDraft.value.avatar,
      system_prompt: localDraft.value.systemPrompt,
      capabilities: {
        supports_code: localDraft.value.capabilities.supportsCode,
        supports_diff: localDraft.value.capabilities.supportsDiff,
        supports_approval: localDraft.value.capabilities.supportsApproval,
        supports_image: localDraft.value.capabilities.supportsImage,
      },
      tags: localDraft.value.tags,
      is_public: localDraft.value.isPublic,
      is_active: localDraft.value.isActive,
      skill_ids: localDraft.value.skillIds,
    }
    let saved: AgentResponse
    if (isEditMode.value) {
      saved = await agentsApi.update(agentId.value!, payload)
    } else {
      saved = await agentsApi.create(payload)
    }
    agentsStore.upsertAgent(saved)
    ElMessage.success(isEditMode.value ? 'Agent updated' : 'Agent created')
    if (!isEditMode.value) {
      router.replace({ name: 'agent-edit', params: { agentId: saved.id } })
    }
  } catch {
    ElMessage.error('Failed to save agent')
  } finally {
    isSaving.value = false
  }
}
</script>
