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
    <ChatInput
      ref="chatInputRef"
      v-model="inputText"
      :agents="agents"
      :reply-to="replyPreview"
      @send="onSend"
      @cancel-reply="onCancelReply"
    />
  </section>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import type { Message, ChatAgent, ReplyPreview } from '@/types/chat'
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
  send: [content: string, mentions: string[], replyToId?: string]
  reply: [messageId: string]
  react: [messageId: string, type: 'like' | 'dislike']
}>()

const inputText = ref('')
const chatInputRef = ref<{ focus: () => void } | null>(null)
const replyPreview = ref<ReplyPreview | null>(null)

const agents = ref<ChatAgent[]>([
  { id: 'orchestrator', name: 'Orchestrator', role: 'Host', status: 'active' },
  { id: 'data-analyst', name: 'Data Analyst', role: 'Processing', status: 'processing' },
  { id: 'lead-developer', name: 'Lead Developer', role: 'Developer', status: 'idle' },
  { id: 'qa-engineer', name: 'QA Engineer', role: 'QA', status: 'idle' },
])

function onSend(content: string, mentions: string[], replyToId?: string) {
  replyPreview.value = null
  emit('send', content, mentions, replyToId)
}

function onReply(messageId: string) {
  const msg = props.messages.find(m => m.id === messageId)
  if (!msg) return

  const senderName = msg.type === 'agent' ? msg.agentName : 'You'
  let previewText = ''
  if (msg.type === 'agent' && msg.blocks?.length) {
    const textBlock = msg.blocks.find(b => b.type === 'text')
    previewText = textBlock ? (textBlock as { content: string }).content : msg.content
  } else {
    previewText = msg.content
  }

  replyPreview.value = {
    messageId,
    senderName,
    content: previewText.slice(0, 80) + (previewText.length > 80 ? '...' : ''),
  }
  emit('reply', messageId)

  nextTick(() => chatInputRef.value?.focus())
}

function onCancelReply() {
  replyPreview.value = null
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