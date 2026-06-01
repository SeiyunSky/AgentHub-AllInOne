<template>
  <section class="flex flex-col bg-surface-elevated h-full overflow-hidden">
    <!-- Header -->
    <ChatHeader v-if="!hideHeader" :title="title" :status="status" :icon="ChatLineRound" variant="brand">
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
      v-if="currentApproval"
      :approval="currentApproval"
      @approve="handleApprove"
      @reject="handleReject"
    />

    <!-- Input -->
    <ChatInput
      v-else
      ref="chatInputRef"
      :model-value="inputText"
      :html-draft="inputHtml"
      :agents="agents"
      :reply-to="replyPreview"
      :streaming="isStreaming"
      @update:model-value="onInputUpdate"
      @send="onSend"
      @stop="onStop"
      @cancel-reply="onCancelReply"
    />
  </section>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import type { Message, ChatAgent } from '@/types/chat'
import type { AgentMember } from '@/types/conversation'
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
  hideHeader?: boolean
}>()

const emit = defineEmits<{
  send: [content: string, mentions: string[], replyToId?: string]
  stop: []
  reply: [messageId: string]
  react: [messageId: string, type: 'like' | 'dislike']
}>()

const chatStore = useChatStore()
const conversationsStore = useConversationsStore()
const chatInputRef = ref<{ focus: () => void } | null>(null)

const convId = computed(() => conversationsStore.currentId)
const isStreaming = computed(() => !!convId.value && chatStore.isStreamingFor(convId.value))
const currentApproval = computed(() => convId.value ? chatStore.getPendingApproval(convId.value) : null)

const inputText = computed(() => convId.value ? chatStore.getInputDraft(convId.value) : '')
const inputHtml = computed(() => convId.value ? chatStore.getInputHtmlDraft(convId.value) : '')
const replyPreview = computed(() => convId.value ? chatStore.getReplyPreview(convId.value) : null)

function onInputUpdate(text: string, html?: string) {
  if (!convId.value) return
  chatStore.setInputDraft(convId.value, text, html)
}

const agents = computed<ChatAgent[]>(() =>
  (conversationsStore.currentConversation?.agents ?? []).map(a => ({
    id: a.id,
    name: a.name,
    role: a.type,
    status: 'active' as const,
  })),
)

function onSend(content: string, mentions: string[], replyToId?: string) {
  if (convId.value) chatStore.setReplyPreview(convId.value, null)
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

  if (!convId.value) return
  chatStore.setReplyPreview(convId.value, {
    messageId,
    senderName,
    content: previewText.slice(0, 80) + (previewText.length > 80 ? '...' : ''),
  })
  emit('reply', messageId)

  nextTick(() => chatInputRef.value?.focus())
}

function onCancelReply() {
  if (convId.value) chatStore.setReplyPreview(convId.value, null)
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
  if (!currentApproval.value || !convId.value) return
  chatStore.resolveApproval(convId.value, currentApproval.value.messageId, currentApproval.value.blockId, 'approved')
}

function handleReject(reason?: string) {
  if (!currentApproval.value || !convId.value) return
  chatStore.resolveApproval(convId.value, currentApproval.value.messageId, currentApproval.value.blockId, 'rejected', reason)
}
</script>
