<template>
  <div class="flex gap-3 justify-end message-enter">
    <div class="max-w-[70%]">
      <div class="p-4 bg-slate-700 text-white rounded-2xl rounded-tr-md shadow-soft">
        <p class="text-[13px] leading-relaxed whitespace-pre-wrap">{{ message.content }}</p>
      </div>
    </div>
    <div class="w-9 h-9 rounded-xl bg-slate-700 flex items-center justify-center text-white text-xs font-bold shrink-0 shadow-soft">
      {{ avatarInitial }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { UserMessage } from '@/types/chat'

const props = defineProps<{
  message: UserMessage
}>()

const avatarInitial = computed(() => 'U')
</script>