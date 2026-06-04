<template>
  <div class="flex gap-3 justify-end message-enter group mb-6">
    <div class="max-w-[70%] relative pb-3">
      <div class="p-4 bg-slate-700 text-white rounded-2xl rounded-tr-md shadow-soft">
        <MarkdownRenderer class="text-[13px] leading-relaxed" :content="message.content" theme="dark" />
      </div>
      <MessageActions
        :message-id="message.id"
        variant="user"
        :content="message.content"
        @reply="$emit('reply', $event)"
        @copy="$emit('copy', $event)"
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
import MarkdownRenderer from '@/components/common/MarkdownRenderer.vue'
import MessageActions from '../MessageActions.vue'

const props = defineProps<{
  message: UserMessage
}>()

defineEmits<{
  reply: [messageId: string]
  copy: [messageId: string]
}>()

const avatarInitial = computed(() => 'U')
</script>