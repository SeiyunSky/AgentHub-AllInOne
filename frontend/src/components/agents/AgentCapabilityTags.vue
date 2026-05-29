<template>
  <div class="flex flex-wrap gap-1.5">
    <span
      v-for="skill in activeSkills"
      :key="skill.key"
      class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium"
      :class="skill.colorClass"
    >
      <el-icon :size="10"><component :is="skill.icon" /></el-icon>
      {{ skill.label }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AgentCapabilities } from '@/types/agent'
import { Cpu, Document, SetUp, Picture } from '@element-plus/icons-vue'
import type { Component } from 'vue'

const props = defineProps<{
  capabilities: AgentCapabilities
}>()

interface SkillDef {
  key: keyof AgentCapabilities
  label: string
  icon: Component
  colorClass: string
}

const skillDefs: SkillDef[] = [
  { key: 'supportsCode', label: 'Code', icon: Cpu, colorClass: 'bg-emerald-50 text-emerald-700' },
  { key: 'supportsDiff', label: 'Diff', icon: Document, colorClass: 'bg-blue-50 text-blue-700' },
  { key: 'supportsApproval', label: 'Approval', icon: SetUp, colorClass: 'bg-amber-50 text-amber-700' },
  { key: 'supportsImage', label: 'Image', icon: Picture, colorClass: 'bg-purple-50 text-purple-700' },
]

const activeSkills = computed(() => skillDefs.filter(s => props.capabilities[s.key]))
</script>
