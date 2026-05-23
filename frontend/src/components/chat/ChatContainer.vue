<template>
  <section class="flex flex-col bg-surface-elevated h-full overflow-hidden">
    <!-- Header -->
    <ChatHeader :title="title" :status="status" :icon="ChatLineRound" variant="brand">
      <template #actions>
        <slot name="headerActions" />
      </template>
    </ChatHeader>

    <!-- Messages -->
    <MessageList class="flex-1 overflow-y-auto custom-scrollbar" :messages="messages" />

    <!-- Input -->
    <ChatInput v-model="inputText" @send="onSend" />
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { Message } from '@/types/chat'
import ChatHeader from '@/components/layout/ChatHeader.vue'
import MessageList from '@/components/chat/MessageList.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import { ChatLineRound } from '@element-plus/icons-vue'

const props = defineProps<{
  title: string
  status?: string
  messages: Message[]
}>()

const emit = defineEmits<{
  send: [content: string]
}>()

const inputText = ref('')

function onSend(content: string) {
  emit('send', content)
}
</script>