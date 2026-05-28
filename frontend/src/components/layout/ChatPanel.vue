<template>
  <ChatContainer
    :title="title"
    :status="statusText"
    :messages="currentMessages"
    @send="onSend"
    @stop="onStop"
    @react="onReact"
  >
    <template #headerActions>
      <el-button circle text size="small" class="!text-on-surface-variant hover:!bg-surface-container">
        <el-icon :size="16"><MoreFilled /></el-icon>
      </el-button>
      <el-button circle text size="small" class="!text-on-surface-variant hover:!bg-surface-container" @click="uiStore.rightPanelVisible = !uiStore.rightPanelVisible">
        <el-icon :size="16">
          <ArrowRight v-if="uiStore.rightPanelVisible" />
          <ArrowLeft v-else />
        </el-icon>
      </el-button>
    </template>
  </ChatContainer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useUIStore } from '@/stores/ui'
import { useChatStore } from '@/stores/chat'
import { useConversationsStore } from '@/stores/conversations'
import { useChat } from '@/composables/useChat'
import { messagesApi } from '@/api/messages'
import ChatContainer from '@/components/chat/ChatContainer.vue'
import { MoreFilled, ArrowRight, ArrowLeft } from '@element-plus/icons-vue'

const uiStore = useUIStore()
const chatStore = useChatStore()
const conversationsStore = useConversationsStore()
const { sendMessage, stopGeneration } = useChat()

const convId = computed(() => conversationsStore.currentId)

const title = computed(() => conversationsStore.currentConversation?.title ?? 'Chat')
const statusText = computed(() => {
  if (chatStore.isStreaming) return 'Streaming...'
  const count = chatStore.activeAgents.length
  return count > 0 ? `${count} agent(s) active` : 'Ready'
})

const currentMessages = computed(() => {
  if (!convId.value) return []
  return chatStore.currentMessages(convId.value)
})

async function onSend(content: string, mentions: string[], _replyToId?: string) {
  await sendMessage(content, mentions)
}

function onStop() {
  stopGeneration()
}

async function onReact(messageId: string, type: 'like' | 'dislike') {
  if (!convId.value) return
  const msgs = chatStore.getMessages(convId.value)
  const current = msgs.find(m => m.id === messageId)?.reaction
  const newReaction = current === type ? undefined : type
  const feedback = newReaction === 'like' ? 'up' as const : newReaction === 'dislike' ? 'down' as const : null
  chatStore.updateReaction(convId.value, messageId, newReaction)
  try {
    await messagesApi.updateFeedback(messageId, feedback)
  } catch {
    chatStore.updateReaction(convId.value, messageId, current)
  }
}
</script>
