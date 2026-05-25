<template>
  <div class="px-4 py-4">
    <div class="text-[10px] uppercase font-semibold text-on-surface-variant tracking-widest mb-3">Projects</div>
    <div class="space-y-2">
      <!-- New Project -->
      <div
        class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-brand hover:bg-brand-light/30 cursor-pointer transition-colors"
      >
        <el-icon :size="16"><Plus /></el-icon>
        <span class="text-[13px] font-medium">New Project</span>
      </div>
      <!-- Projects list -->
      <div
        v-for="project in mockProjects"
        :key="project.id"
        class="group p-3 rounded-xl bg-white border border-outline-variant hover:border-brand hover:bg-brand-light/40 cursor-pointer transition-all duration-200 hover-lift"
      >
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-lg bg-surface-container flex items-center justify-center border border-outline-variant">
            <el-icon class="text-on-surface-variant" :size="16"><FolderOpened /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[13px] font-semibold text-on-surface truncate">{{ project.name }}</p>
            <p class="text-[11px] text-on-surface-variant">{{ project.updatedAt }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { FolderOpened, Plus } from '@element-plus/icons-vue'

const mockProjects = [
  { id: '1', name: 'AgentHub-AllInOne', updatedAt: 'Updated 2h ago' },
  { id: '2', name: 'Web Portal', updatedAt: 'Updated yesterday' },
  { id: '3', name: 'Mobile App', updatedAt: 'Updated 3 days ago' },
]
</script>