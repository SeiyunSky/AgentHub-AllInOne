<template>
  <AppLayout />
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useConversationsStore } from '@/stores/conversations'
import AppLayout from '@/components/layout/AppLayout.vue'

const route = useRoute()
const conversationsStore = useConversationsStore()

async function loadConversation(convId: string) {
  if (conversationsStore.currentId === convId) return
  await conversationsStore.select(convId)
}

onMounted(async () => {
  const convId = route.params.conversationId as string | undefined
  if (convId) {
    await loadConversation(convId)
  } else if (conversationsStore.conversations.length === 0) {
    await conversationsStore.loadList()
  }
})

watch(() => route.params.conversationId, async (newId) => {
  if (newId && typeof newId === 'string') {
    await loadConversation(newId)
  }
})
</script>
