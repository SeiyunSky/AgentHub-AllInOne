<template>
  <div class="px-4 py-4">
    <div class="text-[10px] uppercase font-semibold text-on-surface-variant tracking-widest mb-3">Recent Conversations</div>
    <div class="space-y-2">
      <!-- New Chat -->
      <div
        class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-brand hover:bg-brand-light/30 cursor-pointer transition-colors"
        @click="handleNewChat"
      >
        <el-icon :size="16"><Plus /></el-icon>
        <span class="text-[13px] font-medium">New Chat</span>
      </div>
      <!-- Conversation list -->
      <div
        v-for="conv in conversationsStore.conversations"
        :key="conv.id"
        class="group p-3 rounded-xl bg-white border border-outline-variant hover:border-brand hover:bg-brand-light/40 cursor-pointer transition-all duration-200 hover-lift"
        :class="{ 'list-active !border-brand': conversationsStore.currentId === conv.id }"
        @click="handleSelect(conv.id)"
      >
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-lg bg-gradient-to-br from-brand-light to-brand-subtle flex items-center justify-center shrink-0 border border-brand/20">
            <el-icon class="text-brand" :size="16"><ChatDotRound /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-1">
              <p class="text-[13px] font-semibold text-on-surface truncate">{{ conv.title }}</p>
              <span v-if="conv.is_pinned" class="text-[10px]">📌</span>
            </div>
            <p class="text-[11px] text-on-surface-variant truncate">{{ conv.last_message_preview }}</p>
          </div>
          <div class="flex items-center gap-1">
            <span v-if="conv.unread_count" class="bg-brand text-white text-[10px] font-semibold px-1.5 py-0.5 rounded-full shadow-soft">{{ conv.unread_count }}</span>
            <el-popover
              trigger="click"
              placement="bottom-end"
              :width="160"
              :show-arrow="false"
              :offset="4"
              popper-class="conv-action-popover"
              @click.stop
            >
              <template #reference>
                <button
                  class="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-neutral-200/60 transition-all cursor-pointer"
                  @click.stop
                >
                  <el-icon :size="14" class="text-on-surface-variant"><MoreFilled /></el-icon>
                </button>
              </template>
              <div class="py-1">
                <button class="conv-action-item" @click="handleRename(conv)">
                  <el-icon :size="14"><Edit /></el-icon>
                  <span>Rename</span>
                </button>
                <button class="conv-action-item" @click="handleTogglePin(conv)">
                  <el-icon :size="14"><component :is="conv.is_pinned ? Aim : Promotion" /></el-icon>
                  <span>{{ conv.is_pinned ? 'Unpin' : 'Pin' }}</span>
                </button>
                <button class="conv-action-item" @click="handleToggleArchive(conv)">
                  <el-icon :size="14"><component :is="conv.is_archived ? FolderOpened : Folder" /></el-icon>
                  <span>{{ conv.is_archived ? 'Unarchive' : 'Archive' }}</span>
                </button>
              </div>
            </el-popover>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { ChatDotRound, Plus, MoreFilled, Edit, Aim, Promotion, Folder, FolderOpened } from '@element-plus/icons-vue'
import { useConversationsStore } from '@/stores/conversations'
import type { ConversationListItem } from '@/types/conversation'

const router = useRouter()
const conversationsStore = useConversationsStore()

onMounted(() => {
  conversationsStore.loadList()
})

async function handleNewChat() {
  const conv = await conversationsStore.create('New Chat', 'single', ['orchestrator'])
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
