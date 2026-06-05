<template>
  <div ref="listRef" class="px-5 py-6 space-y-5 overflow-y-auto" @scroll="onScroll">
    <!-- 加载更多指示器 -->
    <div v-if="isLoadingMore" class="flex justify-center py-2 mb-4">
      <el-icon class="animate-spin text-brand" :size="20"><Loading /></el-icon>
    </div>

    <template v-for="msg in messages" :key="msg.id">
      <AgentBubble v-if="msg.type === 'agent'" :message="msg" :streaming="isStreamingMessage(msg)"
        :activity="streamingActivityFor(msg)" :current-tool="streamingToolFor(msg)" @reply="$emit('reply', $event)"
        @copy="$emit('copy', $event)" @react="(id, type) => $emit('react', id, type)" @more="$emit('more', $event)" />
      <UserBubble v-else-if="msg.type === 'user'" :message="msg" @reply="$emit('reply', $event)"
        @copy="$emit('copy', $event)" @react="(id, type) => $emit('react', id, type)" @more="$emit('more', $event)" />
      <!-- Typing indicator -->
      <div v-else-if="msg.type === 'typing'" class="flex gap-3 message-enter">
        <div
          class="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 overflow-hidden bg-gradient-to-br from-brand-light to-brand-subtle border border-brand/20">
          <img v-if="resolveTypingAvatar(msg)" :src="resolveTypingAvatar(msg)!" :alt="msg.agentName" class="w-full h-full object-cover" />
          <span v-else class="text-xs font-bold text-brand">{{ getInitials(msg.agentName) }}</span>
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-[12px] font-semibold text-on-surface">{{ msg.agentName }}</span>
            <span class="text-[10px] text-on-surface-variant">typing</span>
          </div>
          <div
            class="p-4 bg-white border border-outline-variant rounded-2xl rounded-tl-md shadow-soft inline-flex items-center gap-1.5">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import type { Message, AgentMessage } from '@/types/chat'
import { useChatStore } from '@/stores/chat'
import { useConversationsStore } from '@/stores/conversations'
import { useAgentsStore } from '@/stores/agents'
import AgentBubble from './bubbles/AgentBubble.vue'
import UserBubble from './bubbles/UserBubble.vue'

const props = defineProps<{
  messages: Message[]
  /** 老接口:单个 streaming message id;新版本走 chatStore 按 agentId 索引,可同时 N 个 */
  streamingMessageId?: string
  conversationId?: string
}>()

defineEmits<{
  reply: [messageId: string]
  copy: [messageId: string]
  react: [messageId: string, type: 'like' | 'dislike']
  more: [messageId: string]
}>()

const chatStore = useChatStore()
const conversationsStore = useConversationsStore()

/** 判断这条消息是不是某个 Agent 当前正在 streaming 的气泡 */
function isStreamingMessage(msg: AgentMessage): boolean {
  if (props.conversationId) {
    const streaming = chatStore.getAgentStreaming(props.conversationId, msg.agentId)
    if (streaming && streaming.messageId === msg.id) return true
  }
  return msg.id === props.streamingMessageId
}

function streamingActivityFor(msg: AgentMessage): 'thinking' | 'typing' | 'tool' | 'idle' | undefined {
  if (!props.conversationId) return undefined
  const streaming = chatStore.getAgentStreaming(props.conversationId, msg.agentId)
  if (streaming && streaming.messageId === msg.id) return streaming.activity
  return undefined
}

function streamingToolFor(msg: AgentMessage): string | undefined {
  if (!props.conversationId) return undefined
  const streaming = chatStore.getAgentStreaming(props.conversationId, msg.agentId)
  if (streaming && streaming.messageId === msg.id) return streaming.currentTool
  return undefined
}

// 获取首字母
function getInitials(name: string) {
  const words = name.trim().split(/\s+/)
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase()
  return name[0]?.toUpperCase() ?? ''
}

// typing 气泡的头像兜底：消息自带 → store 查 → null
const agentsStore = useAgentsStore()
function resolveTypingAvatar(msg: { agentId: string; avatar?: string }): string | undefined {
  return msg.avatar ?? agentsStore.agents.find(a => a.id === msg.agentId)?.avatar ?? undefined
}

const listRef = ref<HTMLElement>()
const isNearBottom = ref(false)
const pendingScrollToBottom = ref(true)
const isLoadingMore = ref(false)
const hasMoreMessages = ref(true)

// 使用 requestAnimationFrame 节流 scroll 处理函数
// 避免拖动滚动条时高频触发 reflow 导致卡顿
let rafHandle: number | null = null
function onScroll() {
  if (rafHandle) return
  rafHandle = requestAnimationFrame(() => {
    rafHandle = null
    const el = listRef.value
    if (!el) return
    isNearBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 50

    // 向上滚动到顶部时加载更多
    // 只有当内容超出容器高度（有滚动条）时才触发加载
    const hasScrollbar = el.scrollHeight > el.clientHeight
    if (hasScrollbar && el.scrollTop < 100 && !isLoadingMore.value && hasMoreMessages.value && props.messages.length > 0) {
      loadMoreMessages()
    }
  })
}

async function loadMoreMessages() {
  if (!props.conversationId || isLoadingMore.value || !hasMoreMessages.value) return

  const el = listRef.value
  if (!el) return

  isLoadingMore.value = true

  try {
    const oldestMessageId = props.messages[0]?.id
    if (!oldestMessageId) return

    const hasMore = await conversationsStore.loadMoreMessages(props.conversationId, oldestMessageId)
    hasMoreMessages.value = hasMore
  } finally {
    isLoadingMore.value = false
  }
}

function scrollToBottom() {
  const el = listRef.value
  if (!el) return

  el.scrollTo({
    top: el.scrollHeight,
    behavior: 'auto'
  });
}

// Reset when conversation changes, then scroll to bottom after messages load
watch(() => props.conversationId, () => {
  pendingScrollToBottom.value = true
  isNearBottom.value = false
  hasMoreMessages.value = true
  isLoadingMore.value = false
}, { immediate: false })

onUnmounted(() => {
  if (rafHandle !== null) cancelAnimationFrame(rafHandle)
  conversationsStore.currentConversation = null
  conversationsStore.currentId = null
})

watch(
  () => props.messages,
  (newMessages, oldMessages) => {
    // 切换会话后首次加载消息，滚动到底部
    if (pendingScrollToBottom.value && props.messages.length > 0) {
      pendingScrollToBottom.value = false
      // 使用 nextTick 确保 DOM 更新完成
      setTimeout(() => {
        nextTick(() => scrollToBottom()) // so weird
      }, 200)
      
      return
    }

    const isNewMessage = newMessages.length !== oldMessages?.length
    const isUserMessage = newMessages[newMessages.length - 1]?.type === 'user'
    if (isNewMessage && isUserMessage) {
      scrollToBottom()
    } else if (isNearBottom.value) {
      scrollToBottom()
    }
  },
  { immediate:true, flush: 'post' },
)
</script>
