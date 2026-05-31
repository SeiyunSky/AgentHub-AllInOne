<template>
  <div class="px-4 py-4">
    <div class="text-[10px] uppercase font-semibold text-on-surface-variant tracking-widest mb-3">Active Conversations</div>
    <div class="space-y-2">
      <!-- New Chat -->
      <div
        class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-brand hover:bg-brand-light/30 cursor-pointer transition-colors"
        @click="handleNewChat"
      >
        <el-icon :size="16"><Plus /></el-icon>
        <span class="text-[13px] font-medium">New Chat</span>
      </div>
      <!-- New Chat Dialog -->
      <NewChatDialog v-model="showNewChatDialog" @created="handleChatCreated" />

      <!-- Pinned section -->
      <template v-if="pinnedConversations.length">
        <div class="flex items-center gap-1.5 px-1 pt-1">
          <el-icon :size="10" class="text-amber-500 rotate-45"><Promotion /></el-icon>
          <span class="text-[10px] uppercase font-semibold text-amber-500 tracking-widest">Pinned</span>
        </div>
        <div
          v-for="conv in pinnedConversations"
          :key="conv.id"
          class="group p-3 rounded-xl bg-amber-50/60 border border-amber-200/70 hover:border-amber-400 hover:bg-amber-50 cursor-pointer transition-all duration-200 hover-lift"
          :class="{ 'list-active !border-brand !bg-brand-light/40': conversationsStore.currentId === conv.id }"
          @click="handleSelect(conv.id)"
        >
          <ConvItem :conv="conv" @rename="handleRename" @toggle-pin="handleTogglePin" @toggle-archive="handleToggleArchive" />
        </div>
      </template>

      <!-- Recent section -->
      <template v-if="unpinnedConversations.length">
        <div class="flex items-center gap-1.5 px-1 pt-1">
          <span class="text-[10px] uppercase font-semibold text-on-surface-variant tracking-widest">Recent</span>
        </div>
        <div
          v-for="conv in unpinnedConversations"
          :key="conv.id"
          class="group p-3 rounded-xl bg-white border border-outline-variant hover:border-brand hover:bg-brand-light/40 cursor-pointer transition-all duration-200 hover-lift"
          :class="{ 'list-active !border-brand': conversationsStore.currentId === conv.id }"
          @click="handleSelect(conv.id)"
        >
          <ConvItem :conv="conv" @rename="handleRename" @toggle-pin="handleTogglePin" @toggle-archive="handleToggleArchive" />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Plus, Promotion } from '@element-plus/icons-vue'
import { useConversationsStore } from '@/stores/conversations'
import type { ConversationListItem, ConversationResponse } from '@/types/conversation'
import NewChatDialog from '@/components/chat/NewChatDialog.vue'
import ConvItem from './ConversationItem.vue'

const router = useRouter()
const conversationsStore = useConversationsStore()
const showNewChatDialog = ref(false)

const pinnedConversations = computed(() =>
  conversationsStore.conversations.filter(c => c.is_pinned && !c.is_archived),
)
const unpinnedConversations = computed(() =>
  conversationsStore.conversations.filter(c => !c.is_pinned && !c.is_archived),
)

onMounted(() => {
  conversationsStore.loadList()
})

function handleNewChat() {
  showNewChatDialog.value = true
}

function handleChatCreated(conv: ConversationResponse) {
  router.push({ name: 'chat-detail', params: { conversationId: conv.id } })
}

async function handleSelect(id: string) {
  await conversationsStore.select(id)
  router.push({ name: 'chat-detail', params: { conversationId: id } })
}

async function handleRename(conv: ConversationListItem) {
  try {
    const { value } = await ElMessageBox.prompt(conv.title, 'Rename Conversation', {
      confirmButtonText: 'Save',
      cancelButtonText: 'Cancel',
      inputPlaceholder: 'Enter new name',
      customStyle: { borderRadius: '16px' },
    })
    if (value?.trim()) {
      await conversationsStore.update(conv.id, { title: value.trim() })
    }
  } catch {}
}

async function handleTogglePin(conv: ConversationListItem) {
  await conversationsStore.update(conv.id, { is_pinned: !conv.is_pinned })
}

async function handleToggleArchive(conv: ConversationListItem) {
  await conversationsStore.update(conv.id, { is_archived: !conv.is_archived })
}
</script>
