<template>
  <CollapsibleBlock
    :label="title"
    :icon="Files"
    variant="default"
    :badge="`${items.length} items`"
    :default-expanded="defaultExpanded"
  >
    <div class="px-3 py-2 space-y-1.5">
      <div
        v-for="(item, i) in items"
        :key="i"
        class="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-slate-50/80 hover:bg-slate-100/80 transition-colors"
      >
        <el-icon :size="14" class="text-on-surface-variant shrink-0">
          <Document />
        </el-icon>
        <span class="text-[12px] text-on-surface flex-1 truncate">{{ item.name }}</span>
        <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-200/60 text-on-surface-variant shrink-0">{{ item.type }}</span>
      </div>
    </div>
  </CollapsibleBlock>
</template>

<script setup lang="ts">
import { Files, Document } from '@element-plus/icons-vue'
import CollapsibleBlock from './CollapsibleBlock.vue'

withDefaults(defineProps<{
  title: string
  items: Array<{
    name: string
    type: string
    preview?: string
  }>
  defaultExpanded?: boolean
}>(), {
  defaultExpanded: true,
})
</script>