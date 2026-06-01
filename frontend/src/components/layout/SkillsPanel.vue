<template>
  <PanelContainer title="Skills" :icon="MagicStick" variant="brand">
    <template #headerActions>
      <div class="flex items-center gap-2">
        <button
          class="h-8 px-4 rounded-lg flex items-center gap-2 bg-brand text-white text-[13px] font-medium shadow-sm hover:bg-brand-dark transition-colors cursor-pointer"
          @click="router.push({ name: 'skill-create' })"
        >
          <el-icon :size="14"><Plus /></el-icon>
          New Skill
        </button>
      </div>
    </template>

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
        v-if="!isLoading && filteredSkills.length === 0 && skillsStore.skills.length === 0"
        class="flex flex-col items-center justify-center h-full min-h-[400px] fade-in-up"
      >
        <div class="w-20 h-20 rounded-3xl bg-gradient-to-br from-brand-light to-brand-subtle flex items-center justify-center mb-5 shadow-soft">
          <el-icon :size="36" class="text-brand"><MagicStick /></el-icon>
        </div>
        <h3 class="text-[16px] font-semibold text-on-surface mb-1.5">No skills yet</h3>
        <p class="text-[13px] text-on-surface-variant mb-5 text-center max-w-[260px]">
          Create your first skill to define reusable knowledge and behaviors for your agents.
        </p>
        <button class="btn-create" @click="router.push({ name: 'skill-create' })">
          <el-icon :size="14"><Plus /></el-icon>
          Create Skill
        </button>
      </div>

      <!-- No results (has skills but filtered to none) -->
      <div
        v-else-if="!isLoading && filteredSkills.length === 0 && skillsStore.skills.length > 0"
        class="flex flex-col items-center justify-center h-64 text-on-surface-variant fade-in-up"
      >
        <el-icon :size="32" class="opacity-30 mb-3"><Search /></el-icon>
        <p class="text-[13px]">No skills match your filter</p>
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

      <!-- Skill cards grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
        <div
          v-for="skill in filteredSkills"
          :key="skill.id"
          class="premium-card overflow-hidden cursor-pointer hover:-translate-y-0.5"
          @click="router.push({ name: 'skill-edit', params: { skillId: skill.id } })"
        >
          <!-- Brand accent strip -->
          <div class="h-1 bg-gradient-to-r from-brand-light to-brand"></div>

          <div class="p-5">
            <div class="flex items-start gap-3 mb-3">
              <div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 bg-gradient-to-br from-brand-light to-brand-subtle border border-brand/20">
                <el-icon class="text-brand" :size="18"><MagicStick /></el-icon>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-[14px] font-semibold text-on-surface truncate">{{ skill.displayName || skill.name }}</p>
                <p class="text-[11px] text-on-surface-variant truncate">{{ skill.name }}</p>
              </div>
              <div
                class="shrink-0 mt-1.5"
                :class="skill.isActive ? 'status-dot-active agent-pulse' : 'status-dot-inactive'"
                :title="skill.isActive ? 'Active' : 'Inactive'"
              ></div>
            </div>

            <p class="text-[12px] text-on-surface-variant line-clamp-2 mb-3 min-h-[32px]">
              {{ skill.description || 'No description' }}
            </p>

            <!-- Category tag -->
            <div class="flex items-center justify-between">
              <span
                v-if="skill.category"
                class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-surface-container-low text-on-surface-variant"
              >
                {{ skill.category }}
              </span>
              <span v-else class="text-[10px] text-on-surface-variant opacity-50">Uncategorized</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </PanelContainer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { MagicStick, Plus, Search } from '@element-plus/icons-vue'
import { useSkillsStore } from '@/stores/skills'
import PanelContainer from '@/components/layout/PanelContainer.vue'

const router = useRouter()
const skillsStore = useSkillsStore()

const isLoading = ref(false)
const activeFilter = ref('all')

const filterOptions = [
  { label: 'All', value: 'all' },
  { label: '代码', value: '代码' },
  { label: '安全', value: '安全' },
  { label: '领域知识', value: '领域知识' },
  { label: '通用', value: '通用' },
]

const filteredSkills = computed(() => {
  if (activeFilter.value === 'all') return skillsStore.skills
  return skillsStore.skills.filter(s => s.category === activeFilter.value)
})

onMounted(async () => {
  if (skillsStore.skills.length === 0) {
    isLoading.value = true
    try {
      await skillsStore.loadSkills()
    } finally {
      isLoading.value = false
    }
  }
})
</script>
