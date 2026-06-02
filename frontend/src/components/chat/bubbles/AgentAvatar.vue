<template>
  <div
    class="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 overflow-hidden"
    :class="avatar ? '' : avatarClass"
  >
    <img v-if="avatar" :src="avatar" :alt="name" class="w-full h-full object-cover" />
    <template v-else>
      <span v-if="initials" class="text-xs font-bold" :class="textClass">{{ initials }}</span>
      <el-icon v-else :size="16" :class="textClass"><User /></el-icon>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { User } from '@element-plus/icons-vue'

const props = defineProps<{
  name: string
  color?: 'brand' | 'warning' | 'success' | 'error' | 'neutral'
  avatar?: string
}>()

const color = computed(() => props.color ?? 'brand')

const avatarClass = computed(() => ({
  'bg-gradient-to-br from-brand-light to-brand-subtle border border-brand/20 ring-2 ring-brand/10': color.value === 'brand',
  'bg-gradient-to-br from-warning-light to-amber-100 border border-warning/20 ring-2 ring-warning/10': color.value === 'warning',
  'bg-gradient-to-br from-success-light to-emerald-100 border border-success/20': color.value === 'success',
  'bg-gradient-to-br from-error-light to-red-100 border border-error/20': color.value === 'error',
  'bg-surface-container border border-outline-variant': color.value === 'neutral',
}))

const textClass = computed(() => ({
  'text-brand': color.value === 'brand',
  'text-amber-600': color.value === 'warning',
  'text-success': color.value === 'success',
  'text-error': color.value === 'error',
  'text-on-surface-variant': color.value === 'neutral',
}))

const initials = computed(() => {
  const words = props.name.trim().split(/\s+/)
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase()
  return props.name[0]?.toUpperCase() ?? ''
})
</script>