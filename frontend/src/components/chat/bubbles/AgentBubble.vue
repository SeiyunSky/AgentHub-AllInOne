<template>
  <div class="flex gap-3 message-enter">
    <AgentAvatar :name="message.agentName" :color="avatarColor" />

    <div class="flex-1 min-w-0">
      <!-- Header -->
      <div class="flex items-center gap-2 mb-1.5">
        <span class="text-[12px] font-semibold text-on-surface">{{ message.agentName }}</span>
        <span
          v-if="message.agentRole"
          class="text-[10px] font-semibold px-2 py-0.5 rounded-md uppercase"
          :class="roleBadgeClass"
        >{{ message.agentRole }}</span>
        <span class="text-[10px] text-on-surface-variant">{{ timeAgo }}</span>
      </div>

      <!-- Bubble -->
      <div class="p-4 bg-white border border-outline-variant rounded-2xl rounded-tl-md shadow-soft">
        <p class="text-[13px] leading-relaxed text-on-surface whitespace-pre-wrap">{{ message.content }}</p>

        <!-- Code block -->
        <div v-if="message.codeBlock" class="mt-3 rounded-xl overflow-hidden border border-neutral-800">
          <div class="bg-neutral-900 px-3 py-1.5 flex items-center gap-2 border-b border-neutral-800">
            <div class="flex gap-1.5">
              <span class="w-2.5 h-2.5 rounded-full bg-red-500/80"></span>
              <span class="w-2.5 h-2.5 rounded-full bg-yellow-500/80"></span>
              <span class="w-2.5 h-2.5 rounded-full bg-green-500/80"></span>
            </div>
            <span class="text-[10px] text-neutral-500 font-mono ml-1">{{ message.codeBlock.filename }}</span>
          </div>
          <div class="p-3 bg-neutral-900/95 text-xs font-mono leading-relaxed">
            <div v-if="message.codeBlock.diff" class="flex items-center gap-2 mb-1">
              <span class="text-neutral-500 select-none">1</span>
              <span class="text-neutral-400">{{ message.codeBlock.filename }}</span>
              <span class="text-success">+{{ message.codeBlock.diff.added }}</span>
              <span class="text-error">-{{ message.codeBlock.diff.removed }}</span>
            </div>
            <pre class="text-slate-300 whitespace-pre-wrap">{{ message.codeBlock.code }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AgentMessage } from '@/types/chat'
import AgentAvatar from './AgentAvatar.vue'

const props = defineProps<{
  message: AgentMessage
}>()

const avatarColor = computed(() => props.message.agentRoleColor ?? 'brand')

const roleBadgeClass = computed(() => {
  switch (props.message.agentRoleColor) {
    case 'warning': return 'bg-warning-light text-amber-700'
    case 'success': return 'bg-success-light text-success'
    case 'error': return 'bg-error-light text-error'
    default: return 'bg-brand-light text-brand'
  }
})

const timeAgo = computed(() => {
  const now = new Date()
  const diff = now.getTime() - props.message.timestamp.getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  return `${Math.floor(minutes / 60)}h ago`
})
</script>