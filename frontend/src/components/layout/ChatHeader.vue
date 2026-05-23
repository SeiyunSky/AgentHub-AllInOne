<template>
  <div class="px-4 h-12 border-b border-outline-variant flex justify-between items-center shrink-0 bg-white">
    <div class="flex flex-col">
      <h2 class="text-sm font-semibold text-on-surface">{{ title }}</h2>
      <p class="text-[11px] text-on-surface-variant flex items-center gap-1.5">
        <span v-if="status" class="w-1.5 h-1.5 bg-success rounded-full shadow-sm shadow-success/50"></span>
        {{ status }}
      </p>
    </div>
    <div class="flex items-center gap-1">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  status?: string
}>()
</script>