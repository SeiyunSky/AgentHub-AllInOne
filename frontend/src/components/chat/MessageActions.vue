<template>
  <div class="absolute -bottom-4 flex items-center gap-0.5 px-1 py-0.5 rounded-lg bg-white/90 shadow-sm opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none group-hover:pointer-events-auto" :class="variant === 'user' ? 'right-0' : 'left-0'">
    <!-- Like (agent only) -->
    <button
      v-if="variant === 'agent'"
      class="w-7 h-7 rounded-lg flex items-center justify-center cursor-pointer transition-all duration-150"
      :class="reaction === 'like' ? 'text-brand bg-brand/20 scale-110' : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'"
      title="Like"
      @click="handleReact('like')"
    >
      <span class="text-[14px]">😀</span>
    </button>

    <!-- Dislike (agent only) -->
    <button
      v-if="variant === 'agent'"
      class="w-7 h-7 rounded-lg flex items-center justify-center cursor-pointer transition-all duration-150"
      :class="reaction === 'dislike' ? 'text-red-500 bg-red-200 scale-110' : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'"
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
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { ChatRound, DocumentCopy, Select } from '@element-plus/icons-vue'

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
}>()

const copied = ref(false)
const { t } = useI18n()

function handleCopy() {
  navigator.clipboard.writeText(props.content)
  copied.value = true
  emit('copy', props.messageId)
  setTimeout(() => { copied.value = false }, 1500)
}

function handleReact(type: 'like' | 'dislike') {
  const isToggleOff = props.reaction === type
  emit('react', props.messageId, type)
  if (isToggleOff) {
    ElMessage({ message: t('chat.feedbackWithdrawn'), type: 'info', duration: 1500, plain: true })
  } else {
    ElMessage({
      message: type === 'like' ? t('chat.feedbackThumbsUp') : t('chat.feedbackThumbsDown'),
      type: 'success',
      duration: 1500,
      plain: true,
    })
  }
}
</script>
