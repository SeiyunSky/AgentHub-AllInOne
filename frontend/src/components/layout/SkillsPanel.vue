<template>
  <PanelContainer title="Skills" :icon="MagicStick" variant="brand">
    <template #headerActions>
      <div class="flex items-center gap-2">
        <button
          class="h-8 px-4 rounded-lg flex items-center gap-2 bg-brand text-white text-[13px] font-medium shadow-sm hover:bg-brand-dark transition-colors cursor-pointer"
        >
          <el-icon :size="14"><Plus /></el-icon>
          New Skill
        </button>
      </div>
    </template>

    <div class="p-6 overflow-y-auto h-full custom-scrollbar">
      <!-- Empty state -->
      <div
        v-if="!isLoading && skills.length === 0"
        class="flex flex-col items-center justify-center h-64 text-on-surface-variant gap-3"
      >
        <el-icon :size="40" class="opacity-30"><MagicStick /></el-icon>
        <p class="text-[14px]">No skills yet</p>
        <button
          class="px-4 py-2 rounded-lg bg-brand text-white text-[13px] font-medium hover:bg-brand-dark transition-colors cursor-pointer"
        >
          Create your first skill
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

      <!-- Skill cards grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="skill in skills"
          :key="skill.id"
          class="group rounded-2xl border border-outline-variant bg-white p-5 hover:border-brand hover:shadow-card hover:-translate-y-0.5 transition-all duration-200 cursor-pointer"
        >
          <div class="flex items-start gap-3 mb-3">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 bg-gradient-to-br from-brand-light to-brand-subtle border border-brand/20">
              <el-icon class="text-brand" :size="18"><MagicStick /></el-icon>
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-[14px] font-semibold text-on-surface truncate">{{ skill.name }}</p>
              <p class="text-[11px] text-on-surface-variant truncate">{{ skill.description }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </PanelContainer>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { MagicStick, Plus } from '@element-plus/icons-vue'
import { skillsApi } from '@/api/skills'
import PanelContainer from '@/components/layout/PanelContainer.vue'

const skills = ref<{ id: string; name: string; description: string }[]>([])
const isLoading = ref(false)

onMounted(async () => {
  isLoading.value = true
  try {
    skills.value = await skillsApi.list()
  } catch {
    // Skills API may not be available yet
  } finally {
    isLoading.value = false
  }
})
</script>