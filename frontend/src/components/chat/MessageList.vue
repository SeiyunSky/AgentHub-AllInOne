<template>
  <div ref="listRef" class="px-5 py-6 space-y-5" @scroll="onScroll">
    <template v-for="msg in messages" :key="msg.id">
      <AgentBubble
        v-if="msg.type === 'agent'"
        :message="msg"
        @reply="$emit('reply', $event)"
        @copy="$emit('copy', $event)"
        @react="(id, type) => $emit('react', id, type)"
        @more="$emit('more', $event)"
      />
      <UserBubble
        v-else-if="msg.type === 'user'"
        :message="msg"
        @reply="$emit('reply', $event)"
        @copy="$emit('copy', $event)"
        @react="(id, type) => $emit('react', id, type)"
        @more="$emit('more', $event)"
      />
      <!-- Typing indicator -->
      <div v-else-if="msg.type === 'typing'" class="flex gap-3 message-enter">
        <AgentAvatar :name="msg.agentName" color="brand" />
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-[12px] font-semibold text-on-surface">{{ msg.agentName }}</span>
            <span class="text-[10px] text-on-surface-variant">typing</span>
          </div>
          <div class="p-4 bg-white border border-outline-variant rounded-2xl rounded-tl-md shadow-soft inline-flex items-center gap-1.5">
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
import { ref, watch } from 'vue'
import type { Message } from '@/types/chat'
import AgentBubble from './bubbles/AgentBubble.vue'
import UserBubble from './bubbles/UserBubble.vue'
import AgentAvatar from './bubbles/AgentAvatar.vue'

const props = defineProps<{
  messages: Message[]
}>()

defineEmits<{
  reply: [messageId: string]
  copy: [messageId: string]
  react: [messageId: string, type: 'like' | 'dislike']
  more: [messageId: string]
}>()

const listRef = ref<HTMLElement>()
const isNearBottom = ref(false)
let initialized = false

function onScroll() {
  const el = listRef.value
  if (!el) return
  isNearBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 30
}

function scrollToBottom() {
  const el = listRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

watch(
  () => props.messages,
  () => {
    if (!initialized) {
      if (props.messages.length > 0) {
        initialized = true
        onScroll()
      }
      return
    }
    if (isNearBottom.value) {
      scrollToBottom()
    }
  },
  { deep: true, flush: 'post' },
)
</script>