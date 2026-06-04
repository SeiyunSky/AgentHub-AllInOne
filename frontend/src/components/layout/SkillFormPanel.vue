<template>
  <PanelContainer
    :title="isEditMode ? 'Edit Skill' : 'Create Skill'"
    :icon="MagicStick"
    variant="brand"
  >
    <template #headerActions>
      <div class="flex items-center gap-2">
        <span v-if="isReadOnly" class="text-[11px] text-on-surface-variant px-2 py-1 rounded bg-surface-container">
          {{ readOnlyTooltip }}（只读）
        </span>
        <button
          v-if="isEditMode"
          class="h-8 px-4 rounded-lg text-[13px] font-medium border border-red-200 bg-white text-red-500 hover:bg-red-50 hover:border-red-300 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="isDeleting || isReadOnly"
          :title="isReadOnly ? readOnlyTooltip : ''"
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
          :disabled="isSaving || isReadOnly"
          :title="isReadOnly ? readOnlyTooltip : ''"
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
      <SkillForm v-else :draft="localDraft" :edit-mode="isEditMode" :readonly="isReadOnly" />
    </div>
  </PanelContainer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, Loading } from '@element-plus/icons-vue'
import { useSkillsStore } from '@/stores/skills'
import { useAuthStore } from '@/stores/auth'
import { skillsApi, type SkillWithContentResponse } from '@/api/skills'
import type { Skill, SkillDraft } from '@/types/skill'
import PanelContainer from '@/components/layout/PanelContainer.vue'
import SkillForm from '@/components/skills/SkillForm.vue'

const route = useRoute()
const router = useRouter()
const skillsStore = useSkillsStore()
const authStore = useAuthStore()

const isSaving = ref(false)
const isDeleting = ref(false)
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
  isActive: true,
}

const localDraft = ref<SkillDraft>({ ...defaultDraft })
// 当前 skill 的 author_id（SkillDraft 不含此字段，单独存来做权限判断）
const loadedAuthorId = ref<string | null>(null)

// 只读判断：编辑模式下 author 不是当前用户（含内置 GUGA / 他人创建）→ 只读
const isReadOnly = computed(() => {
  if (!isEditMode.value) return false
  if (!loadedAuthorId.value) return false
  return loadedAuthorId.value !== authStore.user?.id
})
const isBuiltin = computed(() => loadedAuthorId.value === 'GUGA')
const readOnlyTooltip = computed(() =>
  isBuiltin.value ? '内置 Skill 不可修改' : '无权修改他人创建的 Skill'
)

function toDraft(raw: SkillWithContentResponse): SkillDraft {
  return {
    name: raw.name,
    displayName: raw.display_name ?? '',
    description: raw.description ?? '',
    category: raw.category ?? '',
    content: raw.content,
    isPublic: raw.is_public,
    isActive: raw.is_active,
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

async function loadSkillById(id: string) {
  isLoading.value = true
  // 清掉旧 author，避免 loading 期间残留上一个 skill 的 readonly 状态
  loadedAuthorId.value = null
  try {
    const raw = await skillsApi.get(id)
    loadedAuthorId.value = raw.author_id ?? null
    localDraft.value = toDraft(raw)
  } catch {
    ElMessage.error('Failed to load skill')
    router.push({ name: 'skills' })
  } finally {
    isLoading.value = false
  }
}

// Load skill data when editing
onMounted(async () => {
  if (isEditMode.value) {
    await loadSkillById(skillId.value!)
  }
})

// Watch route param changes (navigating between different skills)
watch(skillId, async (newId) => {
  if (newId) {
    await loadSkillById(newId)
  } else {
    localDraft.value = { ...defaultDraft }
    loadedAuthorId.value = null
  }
})

function handleCancel() {
  router.push({ name: 'skills' })
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm(
      `Delete skill "${localDraft.value.displayName || localDraft.value.name}"? This cannot be undone.`,
      'Delete Skill',
      { confirmButtonText: 'Delete', cancelButtonText: 'Cancel', type: 'warning' },
    )
  } catch {
    return
  }
  isDeleting.value = true
  try {
    await skillsApi.remove(skillId.value!)
    skillsStore.removeSkill(skillId.value!)
    ElMessage.success('Skill deleted')
    router.push({ name: 'skills' })
  } catch {
    ElMessage.error('Failed to delete skill')
  } finally {
    isDeleting.value = false
  }
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
        is_active: localDraft.value.isActive,
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
