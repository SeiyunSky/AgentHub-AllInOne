<template>
  <el-drawer
    :model-value="modelValue"
    :title="agentId ? 'Edit Agent' : 'Create Agent'"
    direction="rtl"
    size="520px"
    :before-close="handleClose"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="flex flex-col h-full">
      <div class="flex-1 overflow-y-auto">
        <AgentForm :draft="localDraft" />
      </div>
      <div class="px-6 py-4 border-t border-outline-variant flex justify-end gap-2 shrink-0">
        <el-button @click="handleClose">Cancel</el-button>
        <el-button
          type="primary"
          :loading="isSaving"
          @click="handleSave"
        >
          {{ agentId ? 'Save Changes' : 'Create Agent' }}
        </el-button>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { Agent, AgentDraft } from '@/types/agent'
import { agentsApi } from '@/api/agents'
import AgentForm from './AgentForm.vue'

const props = defineProps<{
  modelValue: boolean
  agentId?: string
  initialDraft?: Partial<AgentDraft>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'saved': [agent: Agent]
}>()

const isSaving = ref(false)

const defaultDraft: AgentDraft = {
  name: '',
  description: '',
  type: 'claude',
  systemPrompt: '',
  capabilities: { supportsCode: true, supportsDiff: false, supportsApproval: false, supportsImage: false },
  tags: [],
  isPublic: false,
}

const localDraft = ref<AgentDraft>({ ...defaultDraft, ...props.initialDraft })

watch(() => props.modelValue, async (open) => {
  if (!open) return
  if (props.agentId) {
    try {
      const raw = await agentsApi.get(props.agentId)
      localDraft.value = {
        name: raw.name,
        description: raw.description,
        type: raw.type as any,
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
    }
  } else {
    localDraft.value = { ...defaultDraft, ...props.initialDraft }
  }
})

function handleClose() {
  emit('update:modelValue', false)
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
    if (props.agentId) {
      saved = await agentsApi.update(props.agentId, payload)
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
    emit('saved', agent)
    emit('update:modelValue', false)
    ElMessage.success(props.agentId ? 'Agent updated' : 'Agent created')
  } catch {
    ElMessage.error('Failed to save agent')
  } finally {
    isSaving.value = false
  }
}
</script>
