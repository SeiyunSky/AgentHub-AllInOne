<template>
  <div class="px-4 py-4">
    <div class="text-[10px] uppercase font-semibold text-on-surface-variant tracking-widest mb-3">Skills Library</div>
    <div class="space-y-2">
      <!-- New Skill -->
      <div
        class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-brand hover:bg-brand-light/30 cursor-pointer transition-colors"
      >
        <el-icon :size="16"><Plus /></el-icon>
        <span class="text-[13px] font-medium">New Skill</span>
      </div>
      <!-- Skills list -->
      <div
        v-for="skill in mockSkills"
        :key="skill.id"
        class="group p-3 rounded-xl bg-white border border-outline-variant hover:border-brand hover:bg-brand-light/40 cursor-pointer transition-all duration-200 hover-lift"
      >
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-lg bg-gradient-to-br from-brand-light to-brand-subtle flex items-center justify-center border border-brand/20">
            <el-icon class="text-brand" :size="16"><MagicStick /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[13px] font-semibold text-on-surface truncate">{{ skill.name }}</p>
            <p class="text-[11px] text-on-surface-variant truncate">{{ skill.description }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { MagicStick, Plus } from '@element-plus/icons-vue'

const mockSkills = [
  { id: '1', name: 'Code Review', description: 'Automated code analysis' },
  { id: '2', name: 'Documentation', description: 'Generate docs from code' },
  { id: '3', name: 'Testing', description: 'Write unit tests' },
]
</script>