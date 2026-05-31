<template>
  <PanelContainer title="Projects" :icon="FolderOpened" variant="neutral">
    <template #headerActions>
      <div class="flex items-center gap-2">
        <button
          class="h-8 px-4 rounded-lg flex items-center gap-2 bg-brand text-white text-[13px] font-medium shadow-sm hover:bg-brand-dark transition-colors cursor-pointer"
        >
          <el-icon :size="14"><Plus /></el-icon>
          New Project
        </button>
      </div>
    </template>

    <div class="p-6 overflow-y-auto h-full custom-scrollbar">
      <!-- Empty state -->
      <div
        v-if="projects.length === 0"
        class="flex flex-col items-center justify-center h-64 text-on-surface-variant gap-3"
      >
        <el-icon :size="40" class="opacity-30"><FolderOpened /></el-icon>
        <p class="text-[14px]">No projects yet</p>
        <button
          class="px-4 py-2 rounded-lg bg-brand text-white text-[13px] font-medium hover:bg-brand-dark transition-colors cursor-pointer"
        >
          Create your first project
        </button>
      </div>

      <!-- Project cards -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="project in projects"
          :key="project.id"
          class="group rounded-2xl border border-outline-variant bg-white p-5 hover:border-brand hover:shadow-card hover:-translate-y-0.5 transition-all duration-200 cursor-pointer"
        >
          <div class="flex items-start gap-3 mb-3">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 bg-surface-container border border-outline-variant">
              <el-icon class="text-on-surface-variant" :size="18"><FolderOpened /></el-icon>
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-[14px] font-semibold text-on-surface truncate">{{ project.name }}</p>
              <p class="text-[11px] text-on-surface-variant">{{ project.updatedAt }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </PanelContainer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { FolderOpened, Plus } from '@element-plus/icons-vue'
import PanelContainer from '@/components/layout/PanelContainer.vue'

const projects = ref([
  { id: '1', name: 'AgentHub-AllInOne', updatedAt: 'Updated 2h ago' },
  { id: '2', name: 'Web Portal', updatedAt: 'Updated yesterday' },
  { id: '3', name: 'Mobile App', updatedAt: 'Updated 3 days ago' },
])
</script>