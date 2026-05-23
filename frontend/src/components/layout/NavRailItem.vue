<template>
  <button
    class="w-11 h-11 rounded-xl text-neutral-500 hover:text-white transition-all duration-200 relative group flex items-center justify-center"
    :class="{ 'rail-active': active }"
  >
    <el-icon :size="22"><component :is="icon" /></el-icon>
    <div
      class="absolute left-full ml-3 px-2.5 py-1 bg-neutral-900 text-white text-[11px] font-medium rounded-lg opacity-0 group-hover:opacity-100 whitespace-nowrap z-50 pointer-events-none transition-all duration-200 shadow-float border border-white/10"
    >
      {{ label }}
    </div>
  </button>
</template>

<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  icon: Component
  label: string
  active?: boolean
}>()
</script>
