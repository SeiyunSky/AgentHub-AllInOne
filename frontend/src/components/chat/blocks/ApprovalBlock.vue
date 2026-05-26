<template>
  <CollapsibleBlock
    :label="action"
    :icon="icon"
    :variant="variant"
    :badge="badge"
    :default-expanded="true"
  >
    <div class="px-3 py-2 space-y-2">
      <!-- Detail -->
      <p class="text-[12px] text-on-surface whitespace-pre-wrap">{{ detail }}</p>

      <!-- Status indicators -->
      <div v-if="status === 'approved'" class="flex items-center gap-1.5 text-[11px] text-emerald-600">
        <el-icon :size="12"><CircleCheck /></el-icon>
        <span>Approved{{ decidedAt ? ' at ' + formatTime(decidedAt) : '' }}</span>
      </div>
      <div v-else-if="status === 'rejected'" class="space-y-1">
        <div class="flex items-center gap-1.5 text-[11px] text-red-600">
          <el-icon :size="12"><CircleClose /></el-icon>
          <span>Rejected{{ decidedAt ? ' at ' + formatTime(decidedAt) : '' }}</span>
        </div>
        <p v-if="rejectReason" class="text-[11px] text-red-500 pl-5">{{ rejectReason }}</p>
      </div>
      <div v-else class="flex items-center gap-1.5 text-[11px] text-amber-600">
        <el-icon class="animate-pulse" :size="12"><Warning /></el-icon>
        <span>Waiting for approval...</span>
      </div>
    </div>
  </CollapsibleBlock>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Warning, CircleCheck, CircleClose, Lock } from '@element-plus/icons-vue'
import CollapsibleBlock from './CollapsibleBlock.vue'

const props = defineProps<{
  action: string
  detail: string
  status: 'pending' | 'approved' | 'rejected'
  decidedAt?: string
  rejectReason?: string
}>()

const icon = computed(() => {
  if (props.status === 'approved') return CircleCheck
  if (props.status === 'rejected') return CircleClose
  return Lock
})

const variant = computed(() => {
  if (props.status === 'approved') return 'success'
  if (props.status === 'rejected') return 'error'
  return 'approval'
})

const badge = computed(() => {
  if (props.status === 'approved') return 'approved'
  if (props.status === 'rejected') return 'rejected'
  return 'pending'
})

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString()
}
</script>
