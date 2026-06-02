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
        title="会话设置(成员 / Token 用量)"
        @click="showSettings = true"
      >
        <el-icon :size="14"><Setting /></el-icon>
        <span class="text-[11px] font-medium">设置</span>
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
const { sendMessage, stopGeneration } = useChat()

defineProps<{
  hideHeader?: boolean
}>()

const convId = computed(() => conversationsStore.currentId)
const showSettings = ref(false)

const title = computed(() => conversationsStore.currentConversation?.title ?? 'Chat')

const statusText = computed(() => {
  if (!convId.value) return 'Ready'
  // streaming 中:统计有几个 Agent 同时活跃
  const streamingCount = chatStore.getStreamingAgents(convId.value).length
  if (streamingCount > 0) {
    return streamingCount === 1
      ? '1 个 Agent 正在回复'
      : `${streamingCount} 个 Agent 并行中`
  }
  const agents = conversationsStore.currentConversation?.agents
  const count = agents?.length ?? 0
  return count > 0 ? `${count} 个 Agent · 待命` : 'Ready'
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
    ElMessage({ message: '反馈提交失败，请重试', type: 'error', duration: 2000, plain: true })
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
