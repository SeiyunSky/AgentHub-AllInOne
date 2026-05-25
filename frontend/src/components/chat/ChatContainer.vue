<template>
  <section class="flex flex-col bg-surface-elevated h-full overflow-hidden">
    <!-- Header -->
    <ChatHeader :title="title" :status="status" :icon="ChatLineRound" variant="brand">
      <template #actions>
        <slot name="headerActions" />
      </template>
    </ChatHeader>

    <!-- Messages -->
    <MessageList
      class="flex-1 overflow-y-auto custom-scrollbar"
      :messages="messages"
      @reply="onReply"
      @copy="onCopy"
      @react="onReact"
      @more="onMore"
    />

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
  reply: [messageId: string]
  react: [messageId: string, type: 'like' | 'dislike']
}>()

const inputText = ref('')

function onSend(content: string) {
  emit('send', content)
}

function onReply(messageId: string) {
  const msg = props.messages.find(m => m.id === messageId)
  if (msg) {
    const text = msg.type === 'user' ? msg.content : (msg.content || '')
    inputText.value = `> ${text.slice(0, 80)}${text.length > 80 ? '...' : ''}\n`
  }
  emit('reply', messageId)
}

function onCopy(_messageId: string) {
  // Copy handled inside MessageActions
}

function onReact(messageId: string, type: 'like' | 'dislike') {
  const msg = props.messages.find(m => m.id === messageId)
  if (msg) {
    msg.reaction = msg.reaction === type ? undefined : type
  }
  emit('react', messageId, type)
}

function onMore(messageId: string) {
  console.log('More actions for message:', messageId)
}
</script>