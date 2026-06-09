<template>
  <PanelContainer
    :title="isEditMode ? t('mcpServerFormPanel.editTitle') : t('mcpServerFormPanel.createTitle')"
    :icon="Connection"
    variant="brand"
  >
    <template #headerActions>
      <div class="flex items-center gap-2">
        <span v-if="isReadOnly" class="text-[11px] text-on-surface-variant px-2 py-1 rounded bg-surface-container">
          {{ readOnlyTooltip }}{{ t('mcpServerFormPanel.readonlyTag') }}
        </span>
        <button
          v-if="isEditMode"
          class="h-8 px-4 rounded-lg text-[13px] font-medium border border-red-200 bg-white text-red-500 hover:bg-red-50 hover:border-red-300 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="isDeleting || isReadOnly"
          :title="isReadOnly ? readOnlyTooltip : ''"
          @click="handleDelete"
        >
          <el-icon v-if="isDeleting" :size="14" class="is-loading mr-1.5"><Loading /></el-icon>
          {{ t('mcpServerFormPanel.delete') }}
        </button>
        <button
          v-if="isEditMode"
          class="h-8 px-4 rounded-lg text-[13px] font-medium border border-outline-variant bg-white text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="isTesting"
          @click="handleTest"
        >
          <el-icon v-if="isTesting" :size="14" class="is-loading mr-1.5"><Loading /></el-icon>
          {{ t('mcpServerFormPanel.testConnection') }}
        </button>
        <button
          class="h-8 px-4 rounded-lg text-[13px] font-medium border border-outline-variant bg-white text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-all cursor-pointer"
          @click="handleCancel"
        >
          {{ t('mcpServerFormPanel.cancel') }}
        </button>
        <button
          class="h-8 px-4 rounded-lg text-[13px] font-medium bg-gradient-to-r from-brand to-brand-dark text-white shadow-soft hover:shadow-glow hover:-translate-y-px transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
          :disabled="isSaving || isReadOnly"
          :title="isReadOnly ? readOnlyTooltip : ''"
          @click="handleSave"
        >
          <el-icon v-if="isSaving" :size="14" class="is-loading mr-1.5"><Loading /></el-icon>
          {{ isEditMode ? t('mcpServerFormPanel.saveChanges') : t('mcpServerFormPanel.createServer') }}
        </button>
      </div>
    </template>
    <div class="h-full overflow-y-auto">
      <!-- Test result banner -->
      <div
        v-if="testResult"
        class="mx-6 mt-4 flex items-start gap-2 p-3 rounded-xl text-[12px]"
        :class="testResult.ok ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'"
      >
        <span class="font-semibold shrink-0">{{ testResult.ok ? t('mcpServerFormPanel.testOk') : t('mcpServerFormPanel.testFail') }}</span>
        <span v-if="testResult.ok && testResult.tools.length > 0">
          {{ t('mcpServerFormPanel.toolsFound', { count: testResult.tools.length }) }}: {{ testResult.tools.join(', ') }}
        </span>
        <span v-else-if="testResult.ok">{{ t('mcpServerFormPanel.noToolsFound') }}</span>
        <span v-else>{{ testResult.error }}</span>
      </div>
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
      <MCPServerForm v-else :draft="localDraft" :edit-mode="isEditMode" :readonly="isReadOnly" />
    </div>
  </PanelContainer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, Loading } from '@element-plus/icons-vue'
import { useMCPServersStore } from '@/stores/mcp_servers'
import { useAuthStore } from '@/stores/auth'
import { mcpServersApi, type MCPServerResponse } from '@/api/mcp_servers'
import type { MCPServerDraft, MCPTestResult } from '@/types/mcp_server'
import PanelContainer from '@/components/layout/PanelContainer.vue'
import MCPServerForm from '@/components/mcp_servers/MCPServerForm.vue'

const route = useRoute()
const router = useRouter()
const mcpServersStore = useMCPServersStore()
const authStore = useAuthStore()
const { t } = useI18n()

const isSaving = ref(false)
const isDeleting = ref(false)
const isLoading = ref(false)
const isTesting = ref(false)
const testResult = ref<MCPTestResult | null>(null)
const skipNextLoad = ref(false)

const mcpServerId = computed(() => route.params.mcpServerId as string | undefined)
const isEditMode = computed(() => !!mcpServerId.value)

const loadedAuthorId = ref<string | null>(null)

const isReadOnly = computed(() => {
  if (!isEditMode.value) return false
  if (!loadedAuthorId.value) return false
  return loadedAuthorId.value !== authStore.user?.id
})
const isBuiltin = computed(() => loadedAuthorId.value === 'GUGA')
const readOnlyTooltip = computed(() =>
  isBuiltin.value ? t('mcpServerFormPanel.readonlyBuiltin') : t('mcpServerFormPanel.readonlyOther')
)

const defaultDraft: MCPServerDraft = {
  name: '',
  description: '',
  transport: 'stdio',
  command: '',
  args: [],
  env: {},
  url: '',
  headers: {},
  isPublic: false,
  isActive: true,
}

const localDraft = ref<MCPServerDraft>({ ...defaultDraft, args: [], env: {}, headers: {} })

function toDraft(raw: MCPServerResponse): MCPServerDraft {
  return {
    name: raw.name,
    description: raw.description ?? '',
    transport: raw.transport,
    command: raw.command ?? '',
    args: [...(raw.args ?? [])],
    env: { ...(raw.env ?? {}) },
    url: raw.url ?? '',
    headers: { ...(raw.headers ?? {}) },
    isPublic: raw.is_public,
    isActive: raw.is_active,
  }
}

async function loadById(id: string) {
  isLoading.value = true
  loadedAuthorId.value = null
  testResult.value = null
  try {
    const raw = await mcpServersApi.get(id)
    loadedAuthorId.value = raw.author_id ?? null
    localDraft.value = toDraft(raw)
  } catch {
    ElMessage.error(t('mcpServerFormPanel.loadFailed'))
    router.push({ name: 'mcp-servers' })
  } finally {
    isLoading.value = false
  }
}

onMounted(async () => {
  if (isEditMode.value) {
    await loadById(mcpServerId.value!)
  }
})

watch(mcpServerId, async (newId) => {
  if (newId) {
    if (skipNextLoad.value) {
      skipNextLoad.value = false
      return
    }
    await loadById(newId)
  } else {
    localDraft.value = { ...defaultDraft, args: [], env: {}, headers: {} }
    loadedAuthorId.value = null
    testResult.value = null
  }
})

function handleCancel() {
  router.push({ name: 'mcp-servers' })
}

async function handleTest() {
  if (!mcpServerId.value) return
  isTesting.value = true
  testResult.value = null
  try {
    const result = await mcpServersApi.test(mcpServerId.value)
    testResult.value = result
  } catch {
    testResult.value = { server_id: mcpServerId.value, ok: false, tools: [], error: t('mcpServerFormPanel.testFailed') }
  } finally {
    isTesting.value = false
  }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm(
      t('mcpServerFormPanel.deleteConfirm', { name: localDraft.value.name }),
      t('mcpServerFormPanel.deleteTitle'),
      { confirmButtonText: t('mcpServerFormPanel.delete'), cancelButtonText: t('common.cancel'), type: 'warning' },
    )
  } catch {
    return
  }
  isDeleting.value = true
  try {
    await mcpServersApi.remove(mcpServerId.value!)
    mcpServersStore.removeServer(mcpServerId.value!)
    ElMessage.success(t('mcpServerFormPanel.deleted'))
    router.push({ name: 'mcp-servers' })
  } catch {
    ElMessage.error(t('mcpServerFormPanel.deleteFailed'))
  } finally {
    isDeleting.value = false
  }
}

async function handleSave() {
  if (!localDraft.value.name.trim()) {
    ElMessage.warning(t('mcpServerFormPanel.nameRequired'))
    return
  }
  if (localDraft.value.transport === 'stdio' && !localDraft.value.command?.trim()) {
    ElMessage.warning(t('mcpServerFormPanel.commandRequired'))
    return
  }
  if ((localDraft.value.transport === 'sse' || localDraft.value.transport === 'streamable_http') && !localDraft.value.url?.trim()) {
    ElMessage.warning(t('mcpServerFormPanel.urlRequired'))
    return
  }

  isSaving.value = true
  try {
    let saved: MCPServerResponse
    if (isEditMode.value) {
      saved = await mcpServersApi.update(mcpServerId.value!, {
        name: localDraft.value.name,
        description: localDraft.value.description || undefined,
        transport: localDraft.value.transport,
        command: localDraft.value.command || undefined,
        args: localDraft.value.args,
        env: localDraft.value.env,
        url: localDraft.value.url || undefined,
        headers: localDraft.value.headers,
        is_public: localDraft.value.isPublic,
        is_active: localDraft.value.isActive,
      })
    } else {
      saved = await mcpServersApi.create({
        name: localDraft.value.name,
        description: localDraft.value.description || undefined,
        transport: localDraft.value.transport,
        command: localDraft.value.command || undefined,
        args: localDraft.value.args,
        env: localDraft.value.env,
        url: localDraft.value.url || undefined,
        headers: localDraft.value.headers,
        is_public: localDraft.value.isPublic,
      })
    }
    mcpServersStore.upsertServer(saved)
    ElMessage.success(isEditMode.value ? t('mcpServerFormPanel.updated') : t('mcpServerFormPanel.created'))
    if (!isEditMode.value) {
      skipNextLoad.value = true
      loadedAuthorId.value = authStore.user?.id ?? null
      router.replace({ name: 'mcp-server-edit', params: { mcpServerId: saved.id } })
    }
  } catch {
    ElMessage.error(t('mcpServerFormPanel.saveFailed'))
  } finally {
    isSaving.value = false
  }
}
</script>
