<template>
  <CollapsibleBlock
    :label="title"
    :icon="Promotion"
    :variant="statusVariant"
    :badge="statusBadge"
    :meta="url ? 'live' : undefined"
    :default-expanded="defaultExpanded"
  >
    <div class="px-3 py-2 space-y-3">
      <!-- Progress bar -->
      <div v-if="status === 'deploying' && progress" class="h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          class="h-full bg-gradient-to-r from-blue-500 to-blue-600 progress-fill"
          :style="{ width: `${progress}%` }"
        />
      </div>

      <!-- URL link -->
      <a
        v-if="url && status === 'completed'"
        :href="url"
        target="_blank"
        class="inline-flex items-center gap-1.5 text-[12px] text-blue-600 hover:text-blue-700 transition-colors"
      >
        <el-icon :size="12"><Link /></el-icon>
        <span>{{ url }}</span>
      </a>

      <!-- Logs preview -->
      <div v-if="logs" class="text-[11px]">
        <span class="text-on-surface-variant font-medium">{{ t('deploymentBlock.labelLogs') }}</span>
        <pre class="mt-1 text-slate-600 bg-slate-50 rounded-lg px-2 py-1.5 overflow-x-auto font-mono max-h-24 text-[10px] leading-relaxed">{{ logs }}</pre>
      </div>

      <!-- Status indicator -->
      <div v-if="status === 'deploying'" class="flex items-center gap-2 text-[11px] text-blue-600">
        <el-icon class="animate-spin" :size="12"><Loading /></el-icon>
        <span>{{ t('deploymentBlock.deploying') }}</span>
      </div>

      <div v-else-if="status === 'error'" class="flex items-center gap-2 text-[11px] text-red-600">
        <el-icon :size="12"><CircleClose /></el-icon>
        <span>{{ t('deploymentBlock.failed') }}</span>
      </div>
    </div>
  </CollapsibleBlock>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Promotion, Link, Loading, CircleClose } from '@element-plus/icons-vue'
import CollapsibleBlock from './CollapsibleBlock.vue'

const props = withDefaults(defineProps<{
  title: string
  status: 'deploying' | 'completed' | 'error'
  url?: string
  logs?: string
  progress?: number
  defaultExpanded?: boolean
}>(), {
  defaultExpanded: true,
})

const { t } = useI18n()

const statusVariant = computed(() => {
  if (props.status === 'deploying') return 'tool'
  if (props.status === 'completed') return 'success'
  return 'error'
})

const statusBadge = computed(() => {
  if (props.status === 'deploying') return 'active'
  if (props.status === 'completed') return 'live'
  return 'failed'
})
</script>
