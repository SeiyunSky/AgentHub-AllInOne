<template>
  <PanelContainer :title="t('skillsPanel.title')" :icon="MagicStick" variant="brand">

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
        <h3 class="text-[16px] font-semibold text-on-surface mb-1.5">{{ t('skillsPanel.emptyTitle') }}</h3>
        <p class="text-[13px] text-on-surface-variant mb-5 text-center max-w-[260px]">
          {{ t('skillsPanel.emptyDesc') }}
        </p>
        <button class="btn-create" @click="router.push({ name: 'skill-create' })">
          <el-icon :size="14"><Plus /></el-icon>
          {{ t('skillsPanel.createSkill') }}
        </button>
      </div>

      <!-- No results (has skills but filtered to none) -->
      <div
        v-else-if="!isLoading && filteredSkills.length === 0 && skillsStore.skills.length > 0"
        class="flex flex-col items-center justify-center h-64 text-on-surface-variant fade-in-up"
      >
        <el-icon :size="32" class="opacity-30 mb-3"><Search /></el-icon>
        <p class="text-[13px]">{{ t('skillsPanel.noMatch') }}</p>
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
          :class="categoryStyle[skill.category ?? '']?.card"
          @click="router.push({ name: 'skill-edit', params: { skillId: skill.id } })"
        >
          <!-- Category accent strip -->
          <div
            class="h-1 bg-gradient-to-r"
            :class="categoryStyle[skill.category ?? '']?.strip ?? 'from-brand-light to-brand'"
          ></div>

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
                :title="skill.isActive ? t('skillsPanel.tooltipActive') : t('skillsPanel.tooltipInactive')"
              ></div>
            </div>

            <p class="text-[12px] text-on-surface-variant line-clamp-2 mb-3 min-h-[32px]">
              {{ skill.description || t('skillsPanel.noDescription') }}
            </p>

            <!-- Category tag -->
            <div class="flex items-center justify-between">
              <span
                v-if="skill.category"
                class="px-2 py-0.5 rounded-full text-[10px] font-medium"
                :class="categoryStyle[skill.category]?.tag ?? 'bg-surface-container-low text-on-surface-variant'"
              >
                {{ skill.category }}
              </span>
              <span v-else class="text-[10px] text-on-surface-variant opacity-50">{{ t('skillsPanel.uncategorized') }}</span>
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
import { useI18n } from 'vue-i18n'
import { MagicStick, Plus, Search } from '@element-plus/icons-vue'
import { useSkillsStore } from '@/stores/skills'
import PanelContainer from '@/components/layout/PanelContainer.vue'

const { t } = useI18n()
const router = useRouter()
const skillsStore = useSkillsStore()

const isLoading = ref(false)
const activeFilter = ref('all')

const filterOptions = [
  { label: 'All', value: 'all' },
  { label: '代码实现', value: '代码实现' },
  { label: '数据分析', value: '数据分析' },
  { label: '角色扮演', value: '角色扮演' },
  { label: '容器部署', value: '容器部署' },
  { label: '规则设定', value: '规则设定' },
  { label: '背景说明', value: '背景说明' },
  { label: '通用知识', value: '通用知识' },
]

const categoryStyle: Record<string, { card: string; strip: string; tag: string }> = {
  '代码实现': { card: 'bg-blue-500/5',   strip: 'from-blue-400 to-blue-600',     tag: 'bg-blue-500/10 text-blue-400' },
  '数据分析': { card: 'bg-purple-500/5', strip: 'from-purple-400 to-purple-600', tag: 'bg-purple-500/10 text-purple-400' },
  '角色扮演': { card: 'bg-pink-500/5',   strip: 'from-pink-400 to-pink-600',     tag: 'bg-pink-500/10 text-pink-400' },
  '容器部署': { card: 'bg-teal-500/5',   strip: 'from-teal-400 to-teal-600',     tag: 'bg-teal-500/10 text-teal-400' },
  '规则设定': { card: 'bg-orange-500/5', strip: 'from-orange-400 to-orange-600', tag: 'bg-orange-500/10 text-orange-400' },
  '背景说明': { card: 'bg-yellow-500/5', strip: 'from-yellow-400 to-yellow-500', tag: 'bg-yellow-500/10 text-yellow-400' },
  '通用知识': { card: 'bg-zinc-500/5',   strip: 'from-zinc-400 to-zinc-600',     tag: 'bg-zinc-500/10 text-zinc-400' },
}

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
