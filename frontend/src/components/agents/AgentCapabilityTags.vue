<template>
  <div class="flex flex-wrap gap-1.5">
    <span
      v-for="skill in activeSkills"
      :key="skill.key"
      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium border"
      :class="skill.styleClass"
    >
      <el-icon :size="11"><component :is="skill.icon" /></el-icon>
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
  styleClass: string
}

const skillDefs: SkillDef[] = [
  { key: 'supportsCode', label: 'Code', icon: Cpu, styleClass: 'bg-emerald-50 text-emerald-700 border-emerald-200/60' },
  { key: 'supportsDiff', label: 'Diff', icon: Document, styleClass: 'bg-blue-50 text-blue-700 border-blue-200/60' },
  { key: 'supportsApproval', label: 'Approval', icon: SetUp, styleClass: 'bg-amber-50 text-amber-700 border-amber-200/60' },
  { key: 'supportsImage', label: 'Image', icon: Picture, styleClass: 'bg-purple-50 text-purple-700 border-purple-200/60' },
]

const activeSkills = computed(() => skillDefs.filter(s => props.capabilities[s.key]))
</script>
