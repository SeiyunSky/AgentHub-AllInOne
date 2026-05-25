<template>
  <div class="px-4 py-3 bg-white">
    <div class="bg-surface border border-outline-variant rounded-2xl overflow-hidden focus-within:border-brand focus-within:shadow-glow transition-all duration-200">
      <!-- Textarea -->
      <textarea
        :value="modelValue"
        class="w-full min-h-[80px] max-h-[200px] px-4 pt-3 pb-1 bg-transparent text-[13px] text-on-surface placeholder-on-surface-variant/60 outline-none resize-none leading-relaxed"
        placeholder="Ask Nexus anything..."
        rows="1"
        @input="onInput"
        @keydown.enter.exact="onEnter"
      ></textarea>

      <!-- Bottom action bar -->
      <div class="flex items-center justify-between px-2 py-1.5">
        <!-- Left actions -->
        <div class="flex items-center gap-0.5">
          <button class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant/60 hover:text-on-surface-variant hover:bg-surface-container transition-colors">
            <el-icon :size="18"><Plus /></el-icon>
          </button>
          <button class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant/60 hover:text-on-surface-variant hover:bg-surface-container transition-colors">
            <el-icon :size="18"><Paperclip /></el-icon>
          </button>
        </div>

        <!-- Send button -->
        <button
          class="w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200"
          :class="hasContent ? 'bg-slate-700 text-white hover:bg-slate-600' : 'text-on-surface-variant/40'"
          :disabled="!hasContent"
          @click="onSend"
        >
          <el-icon :size="18"><Promotion /></el-icon>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Plus, Paperclip, Promotion } from '@element-plus/icons-vue'

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: [content: string]
}>()

const hasContent = computed(() => props.modelValue.trim().length > 0)

function onInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLTextAreaElement).value)
}

function onEnter(e: KeyboardEvent) {
  if (!e.shiftKey) {
    e.preventDefault()
    onSend()
  }
}

function onSend() {
  const content = props.modelValue.trim()
  if (!content) return
  emit('send', content)
  emit('update:modelValue', '')
}
</script>