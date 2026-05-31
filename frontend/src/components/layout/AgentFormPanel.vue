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
            <el-button @click="handleCancel">Cancel</el-button>
            <el-button
              type="primary"
              :loading="isSaving"
              @click="handleSave"
            >
              {{ isEditMode ? 'Save Changes' : 'Create Agent' }}
            </el-button>
            <el-button
              circle
              text
              size="small"
              class="!text-on-surface-variant hover:!bg-surface-container"
              @click="toggleChat"
            >
              <el-icon :size="16">
                <ArrowRight v-if="chatVisible" />
                <ArrowLeft v-else />
              </el-icon>
            </el-button>
          </div>
        </template>
        <div class="flex-1 overflow-y-auto">
          <AgentForm :draft="localDraft" />
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
import { ElMessage } from 'element-plus'
import { User, ArrowRight, ArrowLeft } from '@element-plus/icons-vue'
import { Splitpanes, Pane } from 'splitpanes'
import 'splitpanes/dist/splitpanes.css'
import { useAgentsStore } from '@/stores/agents'
import { agentsApi } from '@/api/agents'
import type { Agent, AgentDraft } from '@/types/agent'
import PanelContainer from '@/components/layout/PanelContainer.vue'
import AgentForm from '@/components/agents/AgentForm.vue'
import ChatPanel from '@/components/layout/ChatPanel.vue'

const route = useRoute()
const router = useRouter()
const agentsStore = useAgentsStore()

const isSaving = ref(false)
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
}

const localDraft = ref<AgentDraft>({ ...defaultDraft })

// Load agent data when editing
onMounted(async () => {
  if (isEditMode.value) {
    isLoading.value = true
    try {
      const raw = await agentsApi.get(agentId.value!)
      localDraft.value = {
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
      }
    } catch {
      ElMessage.error('Failed to load agent')
      router.push({ name: 'agents' })
    } finally {
      isLoading.value = false
    }
  } else {
    // Create mode: use initialDraft from store if available (e.g., from AI Builder)
    localDraft.value = { ...defaultDraft, ...agentsStore.initialDraft }
    agentsStore.initialDraft = undefined // clear after use
  }
})

// Also watch route param changes (if navigating between different agents)
watch(agentId, async (newId) => {
  if (newId) {
    isLoading.value = true
    try {
      const raw = await agentsApi.get(newId)
      localDraft.value = {
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
      }
    } catch {
      ElMessage.error('Failed to load agent')
      router.push({ name: 'agents' })
    } finally {
      isLoading.value = false
    }
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
    }
    let saved: any
    if (isEditMode.value) {
      saved = await agentsApi.update(agentId.value!, payload)
    } else {
      saved = await agentsApi.create(payload)
    }
    const agent: Agent = {
      id: saved.id,
      name: saved.name,
      description: saved.description,
      type: saved.type,
      avatar: saved.avatar,
      systemPrompt: saved.system_prompt,
      capabilities: {
        supportsCode: saved.capabilities.supports_code,
        supportsDiff: saved.capabilities.supports_diff,
        supportsApproval: saved.capabilities.supports_approval,
        supportsImage: saved.capabilities.supports_image,
      },
      tags: saved.tags,
      isPublic: saved.is_public,
      isActive: saved.is_active,
      createdAt: new Date(saved.created_at),
      updatedAt: new Date(saved.updated_at),
    }
    // Update store
    const idx = agentsStore.agents.findIndex(a => a.id === saved.id)
    if (idx >= 0) {
      agentsStore.agents.splice(idx, 1, agent)
    } else {
      agentsStore.agents.unshift(agent)
    }
    ElMessage.success(isEditMode.value ? 'Agent updated' : 'Agent created')
    if (!isEditMode.value) {
      // After create, navigate to the edit page for the new agent
      router.replace({ name: 'agent-edit', params: { agentId: saved.id } })
    }
  } catch {
    ElMessage.error('Failed to save agent')
  } finally {
    isSaving.value = false
  }
}
</script>