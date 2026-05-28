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

    <!-- Approval Overlay (replaces input when pending) -->
    <ApprovalOverlay
      v-if="chatStore.pendingApproval"
      :approval="chatStore.pendingApproval"
      @approve="handleApprove"
      @reject="handleReject"
    />

    <!-- Input -->
    <ChatInput
      v-else
      ref="chatInputRef"
      v-model="inputText"
      :agents="agents"
      :reply-to="replyPreview"
      :streaming="isStreaming"
      @send="onSend"
      @stop="onStop"
      @cancel-reply="onCancelReply"
    />
  </section>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import type { Message, ChatAgent, ReplyPreview } from '@/types/chat'
import { useChatStore } from '@/stores/chat'
import { useConversationsStore } from '@/stores/conversations'
import ChatHeader from '@/components/layout/ChatHeader.vue'
import MessageList from '@/components/chat/MessageList.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import ApprovalOverlay from '@/components/chat/ApprovalOverlay.vue'
import { ChatLineRound } from '@element-plus/icons-vue'

const props = defineProps<{
  title: string
  status?: string
  messages: Message[]
}>()

const emit = defineEmits<{
  send: [content: string, mentions: string[], replyToId?: string]
  stop: []
  reply: [messageId: string]
  react: [messageId: string, type: 'like' | 'dislike']
}>()

const chatStore = useChatStore()
const conversationsStore = useConversationsStore()
const inputText = ref('')
const chatInputRef = ref<{ focus: () => void } | null>(null)
const replyPreview = ref<ReplyPreview | null>(null)

const isStreaming = computed(() => chatStore.isStreaming)

const agents = computed<ChatAgent[]>(() =>
  chatStore.activeAgents.map(a => ({ id: a.id, name: a.name, role: a.role, status: a.status })),
)

function onSend(content: string, mentions: string[], replyToId?: string) {
  replyPreview.value = null
  emit('send', content, mentions, replyToId)
}

function onStop() {
  emit('stop')
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
  emit('react', messageId, type)
}

function onMore(messageId: string) {
  console.log('More actions for message:', messageId)
}

function handleApprove() {
  const pa = chatStore.pendingApproval
  if (!pa) return
  const convId = conversationsStore.currentId
  if (!convId) return
  chatStore.resolveApproval(convId, pa.messageId, pa.blockId, 'approved')
}

function handleReject(reason?: string) {
  const pa = chatStore.pendingApproval
  if (!pa) return
  const convId = conversationsStore.currentId
  if (!convId) return
  chatStore.resolveApproval(convId, pa.messageId, pa.blockId, 'rejected', reason)
}
</script>
