<template>
  <ChatContainer
    :title="title"
    :status="statusText"
    :messages="currentMessages"
    :hide-header="hideHeader"
    @send="onSend"
    @stop="onStop"
    @react="onReact"
  >
    <template #headerActions>
      <!-- 会话设置按钮 -->
      <button
        v-if="convId"
        class="settings-btn"
        :class="{ 'settings-btn-active': showSettings }"
        :title="t('conversationSettings.sessionSettingsTitle')"
        @click="showSettings = true"
      >
        <el-icon :size="14"><Setting /></el-icon>
        <span class="text-[11px] font-medium">{{ t('conversationSettings.settings') }}</span>
      </button>

      <el-button
        circle
        text
        size="small"
        class="!text-on-surface-variant hover:!bg-surface-container"
        @click="uiStore.toggleRightPanel()"
      >
        <el-icon :size="16">
          <ArrowRight v-if="uiStore.rightPanelVisible" />
          <ArrowLeft v-else />
        </el-icon>
      </el-button>
    </template>
  </ChatContainer>

  <!-- 会话设置弹窗 -->
  <ConversationSettingsDialog
    v-if="convId"
    v-model="showSettings"
    :conversation-id="convId"
  />
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore } from '@/stores/ui'
import { useChatStore } from '@/stores/chat'
import { useConversationsStore } from '@/stores/conversations'
import { useChat } from '@/composables/useChat'
import { messagesApi } from '@/api/messages'
import { ElMessage } from 'element-plus'
import ChatContainer from '@/components/chat/ChatContainer.vue'
import ConversationSettingsDialog from '@/components/chat/ConversationSettingsDrawer.vue'
import { Setting, ArrowRight, ArrowLeft } from '@element-plus/icons-vue'

const uiStore = useUIStore()
const chatStore = useChatStore()
const conversationsStore = useConversationsStore()
const { t } = useI18n()
const { sendMessage, stopGeneration } = useChat()

defineProps<{
  hideHeader?: boolean
}>()

const convId = computed(() => conversationsStore.currentId)
const showSettings = ref(false)

const title = computed(() => conversationsStore.currentConversation?.title ?? t('chatPanel.defaultTitle'))

const statusText = computed(() => {
  if (!convId.value) return t('chatPanel.readyStatus')
  // streaming 中:统计有几个 Agent 同时活跃
  const streamingCount = chatStore.getStreamingAgents(convId.value).length
  if (streamingCount > 0) {
    return streamingCount === 1
      ? t('chatStatus.oneAgentReplying')
      : `${streamingCount} ${t('chatStatus.multiAgentParallel')}`
  }
  const agents = conversationsStore.currentConversation?.agents
  const count = agents?.length ?? 0
  return count > 0 ? `${count} ${t('chatStatus.multiAgentIdle')}` : t('chatPanel.readyStatus')
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
  // 本地临时消息（streaming 中或用户消息落库前）没有真实 message_id，跳过
  if (messageId.startsWith('local-')) return
  const msgs = chatStore.getMessages(convId.value)
  const current = msgs.find(m => m.id === messageId)?.reaction
  const newReaction = current === type ? undefined : type
  const feedback = newReaction === 'like' ? 'up' as const : newReaction === 'dislike' ? 'down' as const : null
  chatStore.updateReaction(convId.value, messageId, newReaction)
  try {
    await messagesApi.updateFeedback(messageId, feedback)
  } catch {
    chatStore.updateReaction(convId.value, messageId, current)
    ElMessage({ message: t('chat.feedbackFailed'), type: 'error', duration: 2000, plain: true })
  }
}
</script>

<style scoped>
.settings-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid var(--color-outline-variant);
  background: transparent;
  color: var(--color-on-surface-variant);
  cursor: pointer;
  transition: all 0.15s ease;
}
.settings-btn:hover {
  border-color: var(--color-brand);
  color: var(--color-brand);
  background: var(--color-brand-light);
}
.settings-btn-active {
  border-color: var(--color-brand);
  color: var(--color-brand);
  background: var(--color-brand-light);
}
</style>
