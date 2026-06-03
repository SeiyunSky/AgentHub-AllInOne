<template>
  <template v-if="!hasConversation">
    <div class="flex flex-col items-center justify-center h-full gap-4 text-on-surface-variant">
      <el-icon :size="48" class="opacity-30"><ChatLineRound /></el-icon>
      <p class="text-base">从左侧选择或新建聊天</p>
    </div>
  </template>

  <Splitpanes v-else class="splitpanes-theme" @resized="onPaneResized">
    <Pane :size="chatPaneSize" :min-size="chatPaneMinSize" :max-size="chatPaneMaxSize">
      <ChatPanel />
    </Pane>
    <Pane v-if="uiStore.rightPanelVisible" :size="100 - chatPaneSize" :min-size="rightPaneMinSize">
      <RightPanel />
    </Pane>
  </Splitpanes>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useUIStore } from '@/stores/ui'
import { useConversationsStore } from '@/stores/conversations'
import { Splitpanes, Pane } from 'splitpanes'
import 'splitpanes/dist/splitpanes.css'
import { ChatLineRound } from '@element-plus/icons-vue'
import ChatPanel from '@/components/layout/ChatPanel.vue'
import RightPanel from '@/components/layout/RightPanel.vue'

const route = useRoute()
const uiStore = useUIStore()
const conversationsStore = useConversationsStore()

const hasConversation = computed(() => !!route.params.conversationId)

// --- Conversation loading ---

async function loadConversation(convId: string) {
  if (conversationsStore.currentId === convId) return
  await conversationsStore.select(convId)
}

// 路由离开时清除激活状态
watch(() => route.path, (newPath, oldPath) => {
  if (newPath === '/chat') {
    conversationsStore.currentId = null
    conversationsStore.currentConversation = null
  }
})

onMounted(async () => {
  const convId = route.params.conversationId as string | undefined
  if (convId) {
    await loadConversation(convId)
  } else {
    if (conversationsStore.conversations.length === 0) {
      await conversationsStore.loadList({limit: 200})
    }
  }
})

watch(() => route.params.conversationId, async (newId) => {
  if (newId && typeof newId === 'string') {
    await loadConversation(newId)
  }
})

// --- Splitpanes (moved from AppLayout) ---

const chatPaneSize = computed(() => uiStore.chatPanePercent)
const chatPaneMinSize = 35
const chatPaneMaxSize = undefined
const rightPaneMinSize = 25

function onPaneResized(event: ({ min: number; max: number; size: number })[]) {
  if (event.length > 0) {
    uiStore.setChatPanePercent(event[0].size)
  }
}
</script>
