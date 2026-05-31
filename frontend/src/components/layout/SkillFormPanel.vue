<template>
  <PanelContainer
    :title="isEditMode ? 'Edit Skill' : 'Create Skill'"
    :icon="MagicStick"
    variant="brand"
  >
    <template #headerActions>
      <div class="flex items-center gap-2">
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
          {{ isEditMode ? 'Save Changes' : 'Create Skill' }}
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
      <SkillForm v-else :draft="localDraft" :edit-mode="isEditMode" />
    </div>
  </PanelContainer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MagicStick, Loading } from '@element-plus/icons-vue'
import { useSkillsStore } from '@/stores/skills'
import { skillsApi, type SkillWithContentResponse } from '@/api/skills'
import type { Skill, SkillDraft } from '@/types/skill'
import PanelContainer from '@/components/layout/PanelContainer.vue'
import SkillForm from '@/components/skills/SkillForm.vue'

const route = useRoute()
const router = useRouter()
const skillsStore = useSkillsStore()

const isSaving = ref(false)
const isLoading = ref(false)

const skillId = computed(() => route.params.skillId as string | undefined)
const isEditMode = computed(() => !!skillId.value)

const defaultDraft: SkillDraft = {
  name: '',
  displayName: '',
  description: '',
  category: '',
  content: '',
  isPublic: false,
}

const localDraft = ref<SkillDraft>({ ...defaultDraft })

function toDraft(raw: SkillWithContentResponse): SkillDraft {
  return {
    name: raw.name,
    displayName: raw.display_name ?? '',
    description: raw.description ?? '',
    category: raw.category ?? '',
    content: raw.content,
    isPublic: raw.is_public,
  }
}

function toSkill(raw: SkillWithContentResponse): Skill {
  return {
    id: raw.id,
    name: raw.name,
    displayName: raw.display_name,
    description: raw.description,
    category: raw.category,
    authorId: raw.author_id,
    isPublic: raw.is_public,
    isActive: raw.is_active,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  }
}

// Load skill data when editing
onMounted(async () => {
  if (isEditMode.value) {
    isLoading.value = true
    try {
      const raw = await skillsApi.get(skillId.value!)
      localDraft.value = toDraft(raw)
    } catch {
      ElMessage.error('Failed to load skill')
      router.push({ name: 'skills' })
    } finally {
      isLoading.value = false
    }
  }
})

// Watch route param changes (navigating between different skills)
watch(skillId, async (newId) => {
  if (newId) {
    isLoading.value = true
    try {
      const raw = await skillsApi.get(newId)
      localDraft.value = toDraft(raw)
    } catch {
      ElMessage.error('Failed to load skill')
      router.push({ name: 'skills' })
    } finally {
      isLoading.value = false
    }
  } else {
    localDraft.value = { ...defaultDraft }
  }
})

function handleCancel() {
  router.push({ name: 'skills' })
}

async function handleSave() {
  if (!localDraft.value.name.trim()) {
    ElMessage.warning('Skill name is required')
    return
  }
  if (!/^[a-z0-9_-]+$/.test(localDraft.value.name)) {
    ElMessage.warning('Skill name must be lowercase letters, numbers, hyphens, or underscores')
    return
  }
  if (!localDraft.value.content.trim()) {
    ElMessage.warning('Skill content is required')
    return
  }

  isSaving.value = true
  try {
    let saved: SkillWithContentResponse
    if (isEditMode.value) {
      const updatePayload = {
        display_name: localDraft.value.displayName || undefined,
        description: localDraft.value.description || undefined,
        category: localDraft.value.category || undefined,
        content: localDraft.value.content,
        is_public: localDraft.value.isPublic,
      }
      saved = await skillsApi.update(skillId.value!, updatePayload)
    } else {
      const createPayload = {
        name: localDraft.value.name,
        display_name: localDraft.value.displayName || undefined,
        description: localDraft.value.description || undefined,
        category: localDraft.value.category || undefined,
        content: localDraft.value.content,
        is_public: localDraft.value.isPublic,
      }
      saved = await skillsApi.create(createPayload)
    }

    // Update store
    const skill = toSkill(saved)
    const idx = skillsStore.skills.findIndex(s => s.id === saved.id)
    if (idx >= 0) {
      skillsStore.skills.splice(idx, 1, skill)
    } else {
      skillsStore.skills.unshift(skill)
    }

    ElMessage.success(isEditMode.value ? 'Skill updated' : 'Skill created')

    if (!isEditMode.value) {
      router.replace({ name: 'skill-edit', params: { skillId: saved.id } })
    }
  } catch {
    ElMessage.error('Failed to save skill')
  } finally {
    isSaving.value = false
  }
}
</script>
