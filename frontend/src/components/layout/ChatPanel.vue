<template>
  <section
    class="flex flex-col border-r border-outline-variant bg-surface-elevated h-full overflow-hidden"
  >
    <!-- Header -->
    <ChatHeader />

    <!-- Messages -->
    <MessageList class="flex-1 overflow-y-auto custom-scrollbar" />

    <!-- Input -->
    <ChatInput />
  </section>
</template>

<script setup lang="ts">
import ChatHeader from './ChatHeader.vue'
import MessageList from '@/components/chat/MessageList.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
</script>