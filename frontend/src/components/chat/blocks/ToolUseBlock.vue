<template>
  <CollapsibleBlock
    :label="toolName"
    :icon="Cpu"
    :variant="statusVariant"
    :badge="statusBadge"
    :default-expanded="defaultExpanded"
  >
    <div class="px-3 py-2 space-y-2">
      <!-- Input -->
      <div v-if="input" class="text-[11px]">
        <span class="text-on-surface-variant font-medium">Input:</span>
        <pre class="mt-1 text-slate-600 bg-slate-50 rounded-lg px-2 py-1.5 overflow-x-auto font-mono">{{ formatInput(input) }}</pre>
      </div>

      <!-- Output -->
      <div v-if="output" class="text-[11px]">
        <span class="text-on-surface-variant font-medium">Output:</span>
        <pre class="mt-1 text-emerald-600 bg-emerald-50/50 rounded-lg px-2 py-1.5 overflow-x-auto whitespace-pre-wrap">{{ output }}</pre>
      </div>

      <!-- Running indicator -->
      <div v-if="status === 'running'" class="flex items-center gap-2 text-[11px] text-blue-600">
        <el-icon class="animate-spin" :size="12"><Loading /></el-icon>
        <span>Executing...</span>
      </div>
    </div>
  </CollapsibleBlock>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Cpu, Loading } from '@element-plus/icons-vue'
import CollapsibleBlock from './CollapsibleBlock.vue'

const props = withDefaults(defineProps<{
  toolName: string
  input?: Record<string, unknown>
  output?: string
  status: 'running' | 'completed' | 'error'
  defaultExpanded?: boolean
}>(), {
  defaultExpanded: false,
})

const statusVariant = computed(() => {
  if (props.status === 'running') return 'tool'
  if (props.status === 'completed') return 'success'
  return 'error'
})

const statusBadge = computed(() => {
  if (props.status === 'running') return 'running'
  if (props.status === 'completed') return 'done'
  return 'error'
})

function formatInput(input: Record<string, unknown>): string {
  return JSON.stringify(input, null, 2)
}
</script>