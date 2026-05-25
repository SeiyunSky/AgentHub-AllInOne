<template>
  <div class="flex items-center gap-0.5 mt-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200" :class="variant === 'user' ? 'justify-end' : ''">
    <!-- Like -->
    <button
      class="w-7 h-7 rounded-lg flex items-center justify-center cursor-pointer transition-colors"
      :class="reaction === 'like' ? 'text-brand bg-brand-light/50' : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'"
      title="Like"
      @click="handleReact('like')"
    >
      <span class="text-[14px]">😀</span>
    </button>

    <!-- Dislike -->
    <button
      class="w-7 h-7 rounded-lg flex items-center justify-center cursor-pointer transition-colors"
      :class="reaction === 'dislike' ? 'text-red-500 bg-red-50' : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'"
      title="Dislike"
      @click="handleReact('dislike')"
    >
      <span class="text-[14px]">🙁</span>
    </button>

    <!-- Reply -->
    <button
      class="w-7 h-7 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface cursor-pointer transition-colors"
      title="Reply"
      @click="$emit('reply', messageId)"
    >
      <el-icon :size="14"><ChatRound /></el-icon>
    </button>

    <!-- Copy -->
    <button
      class="w-7 h-7 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface cursor-pointer transition-colors"
      title="Copy"
      @click="handleCopy"
    >
      <el-icon :size="14"><component :is="copied ? Select : DocumentCopy" /></el-icon>
    </button>

    <!-- More -->
    <button
      class="w-7 h-7 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface cursor-pointer transition-colors"
      title="More"
      @click="$emit('more', messageId)"
    >
      <el-icon :size="14"><MoreFilled /></el-icon>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ChatRound, DocumentCopy, Select, MoreFilled } from '@element-plus/icons-vue'

const props = defineProps<{
  messageId: string
  variant: 'agent' | 'user'
  content: string
  reaction?: 'like' | 'dislike'
}>()

const emit = defineEmits<{
  reply: [messageId: string]
  copy: [messageId: string]
  react: [messageId: string, type: 'like' | 'dislike']
  more: [messageId: string]
}>()

const copied = ref(false)

function handleCopy() {
  navigator.clipboard.writeText(props.content)
  copied.value = true
  emit('copy', props.messageId)
  setTimeout(() => { copied.value = false }, 1500)
}

function handleReact(type: 'like' | 'dislike') {
  emit('react', props.messageId, props.reaction === type ? ('none' as any) : type)
}
</script>