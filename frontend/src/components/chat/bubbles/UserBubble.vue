<template>
  <div class="flex gap-3 justify-end message-enter group">
    <div class="max-w-[70%]">
      <div class="p-4 bg-slate-700 text-white rounded-2xl rounded-tr-md shadow-soft">
        <p class="text-[13px] leading-relaxed whitespace-pre-wrap">{{ message.content }}</p>
      </div>
      <MessageActions
        :message-id="message.id"
        variant="user"
        :content="message.content"
        :reaction="message.reaction"
        @reply="$emit('reply', $event)"
        @copy="$emit('copy', $event)"
        @react="(id, type) => $emit('react', id, type)"
        @more="$emit('more', $event)"
      />
    </div>
    <div class="w-9 h-9 rounded-xl bg-slate-700 flex items-center justify-center text-white text-xs font-bold shrink-0 shadow-soft">
      {{ avatarInitial }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { UserMessage } from '@/types/chat'
import MessageActions from '../MessageActions.vue'

const props = defineProps<{
  message: UserMessage
}>()

defineEmits<{
  reply: [messageId: string]
  copy: [messageId: string]
  react: [messageId: string, type: 'like' | 'dislike']
  more: [messageId: string]
}>()

const avatarInitial = computed(() => 'U')
</script>