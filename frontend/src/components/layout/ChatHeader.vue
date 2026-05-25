<template>
  <div class="h-14 px-4 flex justify-between items-center shrink-0 bg-white">
    <!-- Left: icon + title + status -->
    <div class="flex items-center gap-2.5">
      <div v-if="icon" class="w-7 h-7 rounded-lg flex items-center justify-center" :class="iconContainerClass">
        <el-icon :size="14" :class="iconTextClass">
          <component :is="icon" />
        </el-icon>
      </div>
      <div class="flex flex-col">
        <h2 class="text-[14px] font-semibold text-on-surface leading-tight">{{ title }}</h2>
        <p v-if="status" class="text-[10px] text-on-surface-variant flex items-center gap-1.5 leading-tight">
          <span v-if="statusDot" class="w-1.5 h-1.5 rounded-full" :class="dotClass"></span>
          {{ status }}
        </p>
      </div>
    </div>
    <!-- Right: actions -->
    <div class="flex items-center gap-0.5">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'

const props = withDefaults(defineProps<{
  title: string
  status?: string
  icon?: Component
  variant?: 'brand' | 'success' | 'warning' | 'error' | 'neutral'
  statusDot?: boolean
}>(), {
  variant: 'brand',
  statusDot: true,
})

const iconContainerClass = computed(() => {
  switch (props.variant) {
    case 'success': return 'bg-emerald-50'
    case 'warning': return 'bg-amber-50'
    case 'error': return 'bg-red-50'
    case 'neutral': return 'bg-slate-100'
    default: return 'bg-blue-50'
  }
})

const iconTextClass = computed(() => {
  switch (props.variant) {
    case 'success': return 'text-emerald-500'
    case 'warning': return 'text-amber-500'
    case 'error': return 'text-red-500'
    case 'neutral': return 'text-slate-400'
    default: return 'text-blue-500'
  }
})

const dotClass = computed(() => 'bg-emerald-400')
</script>