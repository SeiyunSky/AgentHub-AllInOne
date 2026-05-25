<template>
  <button
    class="w-full flex items-center gap-2.5 py-2.5 px-3 rounded-lg cursor-pointer transition-all duration-200"
    :class="active
      ? 'text-white bg-white/10'
      : 'text-white/50 hover:text-white/80 hover:bg-white/5'"
  >
    <el-icon :size="20"><component :is="icon" /></el-icon>
    <span class="text-[13px] font-medium leading-none">{{ label }}</span>
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