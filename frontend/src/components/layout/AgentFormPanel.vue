<template>
  <Splitpanes class="splitpanes-theme" @resized="onPaneResized">
    <Pane :size="chatPaneSize" :min-size="35">
      <PanelContainer
        :title="isEditMode ? t('agentFormPanel.editTitle') : t('agentFormPanel.createTitle')"
        :icon="User"
        variant="brand"
      >
        <template #headerActions>
          <div class="flex items-center gap-2">
            <span v-if="isReadOnly" class="text-[11px] text-on-surface-variant px-2 py-1 rounded bg-surface-container">
              {{ readOnlyTooltip }}{{ t('agentFormPanel.readonlyTag') }}
            </span>
            <button
              v-if="isEditMode"
              class="h-8 px-4 rounded-lg text-[13px] font-medium border border-red-200 bg-white text-red-500 hover:bg-red-50 hover:border-red-300 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isDeleting || isReadOnly"
              :title="isReadOnly ? readOnlyTooltip : ''"
              @click="handleDelete"
            >
              <el-icon v-if="isDeleting" :size="14" class="is-loading mr-1.5"><Loading /></el-icon>
              {{ t('agentFormPanel.delete') }}
            </button>
            <button
              class="h-8 px-4 rounded-lg text-[13px] font-medium border border-outline-variant bg-white text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-all cursor-pointer"
              @click="handleCancel"
            >
              {{ t('agentFormPanel.cancel') }}
            </button>
            <button
              class="h-8 px-4 rounded-lg text-[13px] font-medium bg-gradient-to-r from-brand to-brand-dark text-white shadow-soft hover:shadow-glow hover:-translate-y-px transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
              :disabled="isSaving || isReadOnly"
              :title="isReadOnly ? readOnlyTooltip : ''"
              @click="handleSave"
            >
              <el-icon v-if="isSaving" :size="14" class="is-loading mr-1.5"><Loading /></el-icon>
              {{ isEditMode ? t('agentFormPanel.saveChanges') : t('agentFormPanel.createAgent') }}
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
          <AgentForm v-else :draft="localDraft" :edit-mode="isEditMode" :readonly="isReadOnly" />
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
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, ArrowRight, ArrowLeft, Loading } from '@element-plus/icons-vue'
import { Splitpanes, Pane } from 'splitpanes'
import 'splitpanes/dist/splitpanes.css'
import { useAgentsStore } from '@/stores/agents'
import { useAuthStore } from '@/stores/auth'
import { agentsApi, type AgentResponse } from '@/api/agents'
import type { AgentDraft } from '@/types/agent'
import PanelContainer from '@/components/layout/PanelContainer.vue'
import AgentForm from '@/components/agents/AgentForm.vue'
import ChatPanel from '@/components/layout/ChatPanel.vue'

const route = useRoute()
const router = useRouter()
const agentsStore = useAgentsStore()
const authStore = useAuthStore()
const { t } = useI18n()

// 只读判断：编辑模式下，owner 不是当前用户（含内置 GUGA 资源 / 他人创建）→ 只读
const isReadOnly = computed(() => {
  if (!isEditMode.value) return false
  if (!loadedOwnerId.value) return false
  return loadedOwnerId.value !== authStore.user?.id
})
const isBuiltin = computed(() => loadedOwnerId.value === 'GUGA')
const readOnlyTooltip = computed(() =>
  isBuiltin.value ? t('agentFormPanel.readonlyBuiltin') : t('agentFormPanel.readonlyOther')
)

const isSaving = ref(false)
const isDeleting = ref(false)
const isLoading = ref(false)
const chatVisible = ref(false)
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
  mcpServerIds: [],
}

const localDraft = ref<AgentDraft>({ ...defaultDraft })
// 当前 agent 的 owner user_id（从 API 返回的 raw 拿，AgentDraft 不包含此字段）。
// 用于判断是否可写：当前用户 id !== owner 时只读（包括内置 GUGA 资源）
const loadedOwnerId = ref<string | null>(null)

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
    mcpServerIds: raw.mcp_server_ids ?? [],
  }
}

async function loadAgentById(id: string) {
  isLoading.value = true
  // 切换 agent 时立刻清掉旧 owner，避免 loading 期间用上一个 agent 的 readonly 状态
  loadedOwnerId.value = null
  try {
    const raw = await agentsApi.get(id)
    loadedOwnerId.value = raw.user_id ?? null
    localDraft.value = rawToDraft(raw)
  } catch {
    ElMessage.error(t('agentFormPanel.loadFailed'))
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
  router.back()
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
      t('agentFormPanel.deleteConfirm', { name: localDraft.value.name }),
      t('agentFormPanel.deleteTitle'),
      { confirmButtonText: t('agentFormPanel.delete'), cancelButtonText: t('common.cancel'), type: 'warning' },
    )
  } catch {
    return
  }
  isDeleting.value = true
  try {
    await agentsApi.delete(agentId.value!)
    agentsStore.removeAgent(agentId.value!)
    ElMessage.success(t('agentFormPanel.deleted'))
    router.back()
  } catch {
    ElMessage.error(t('agentFormPanel.deleteFailed'))
  } finally {
    isDeleting.value = false
  }
}

async function handleSave() {
  if (!localDraft.value.name.trim()) {
    ElMessage.warning(t('agentFormPanel.nameRequired'))
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
      mcp_server_ids: localDraft.value.mcpServerIds,
    }
    let saved: AgentResponse
    if (isEditMode.value) {
      saved = await agentsApi.update(agentId.value!, payload)
    } else {
      saved = await agentsApi.create(payload)
    }
    agentsStore.upsertAgent(saved)
    ElMessage.success(isEditMode.value ? t('agentFormPanel.updated') : t('agentFormPanel.created'))
    if (!isEditMode.value) {
      router.replace({ name: 'agent-edit', params: { agentId: saved.id } })
    } else {
      router.back()
    }
  } catch {
    ElMessage.error(t('agentFormPanel.saveFailed'))
  } finally {
    isSaving.value = false
  }
}
</script>
