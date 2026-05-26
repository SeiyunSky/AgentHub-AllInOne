<template>
  <div class="rounded-xl border overflow-hidden transition-colors" :class="containerClass">
    <!-- Header -->
    <button
      class="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-black/[0.02] transition-colors cursor-pointer"
      @click="toggle"
    >
      <el-icon :size="14" class="transition-transform duration-200 shrink-0" :class="{ 'rotate-90': expanded }">
        <ArrowRight />
      </el-icon>
      <el-icon v-if="icon" :size="14" class="shrink-0" :class="iconColor">
        <component :is="icon" />
      </el-icon>
      <span class="text-[12px] font-medium truncate" :class="labelColor">{{ label }}</span>
      <span v-if="badge" class="text-[10px] px-1.5 py-0.5 rounded-full shrink-0" :class="badgeClass">{{ badge }}</span>
      <div class="flex-1" />
      <slot name="actions" />
      <span v-if="meta" class="text-[10px] text-on-surface-variant shrink-0">{{ meta }}</span>
    </button>

    <!-- Content -->
    <div v-show="expanded" class="border-t" :class="borderClass">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'
import type { Component } from 'vue'

const props = withDefaults(defineProps<{
  label: string
  icon?: Component
  variant?: 'default' | 'thinking' | 'tool' | 'code' | 'artifact' | 'success' | 'error' | 'image' | 'approval'
  badge?: string
  meta?: string
  defaultExpanded?: boolean
}>(), {
  variant: 'default',
  defaultExpanded: false,
})

const expanded = ref(props.defaultExpanded)

function toggle() {
  expanded.value = !expanded.value
}

const containerClass = computed(() => {
  switch (props.variant) {
    case 'thinking': return 'border-purple-200/60 bg-purple-50/30'
    case 'tool': return 'border-blue-200/60 bg-blue-50/30'
    case 'code': return 'border-neutral-200/60 bg-neutral-50/30'
    case 'artifact': return 'border-violet-200/60 bg-violet-50/30'
    case 'success': return 'border-emerald-200/60 bg-emerald-50/30'
    case 'error': return 'border-red-200/60 bg-red-50/30'
    case 'image': return 'border-sky-200/60 bg-sky-50/30'
    case 'approval': return 'border-amber-200/60 bg-amber-50/30'
    default: return 'border-outline-variant bg-white'
  }
})

const iconColor = computed(() => {
  switch (props.variant) {
    case 'thinking': return 'text-purple-500'
    case 'tool': return 'text-blue-500'
    case 'code': return 'text-neutral-500'
    case 'artifact': return 'text-violet-500'
    case 'success': return 'text-emerald-500'
    case 'error': return 'text-red-500'
    case 'image': return 'text-sky-500'
    case 'approval': return 'text-amber-500'
    default: return 'text-on-surface-variant'
  }
})

const labelColor = computed(() => {
  switch (props.variant) {
    case 'thinking': return 'text-purple-700'
    case 'tool': return 'text-blue-700'
    case 'artifact': return 'text-violet-700'
    case 'success': return 'text-emerald-700'
    case 'error': return 'text-red-700'
    case 'approval': return 'text-amber-700'
    default: return 'text-on-surface'
  }
})

const borderClass = computed(() => {
  switch (props.variant) {
    case 'thinking': return 'border-purple-100'
    case 'tool': return 'border-blue-100'
    case 'code': return 'border-neutral-100'
    case 'artifact': return 'border-violet-100'
    case 'success': return 'border-emerald-100'
    case 'error': return 'border-red-100'
    case 'approval': return 'border-amber-100'
    default: return 'border-outline-variant'
  }
})

const badgeClass = computed(() => {
  switch (props.variant) {
    case 'thinking': return 'bg-purple-100 text-purple-600'
    case 'tool': return 'bg-blue-100 text-blue-600'
    case 'artifact': return 'bg-violet-100 text-violet-600'
    case 'success': return 'bg-emerald-100 text-emerald-600'
    case 'error': return 'bg-red-100 text-red-600'
    case 'approval': return 'bg-amber-100 text-amber-600'
    default: return 'bg-surface-container text-on-surface-variant'
  }
})
</script>
