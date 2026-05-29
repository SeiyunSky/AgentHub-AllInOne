<template>
  <div class="flex items-center gap-3">
    <!-- Avatar with unread badge -->
    <div class="relative shrink-0">
      <div class="w-9 h-9 rounded-lg bg-gradient-to-br from-brand-light to-brand-subtle flex items-center justify-center border border-brand/20">
        <el-icon class="text-brand" :size="16"><ChatDotRound /></el-icon>
      </div>
      <span
        v-if="conv.unread_count"
        class="absolute -top-1.5 -right-1.5 min-w-[16px] h-4 bg-brand text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1 shadow-sm ring-2 ring-white"
      >{{ conv.unread_count > 99 ? '99+' : conv.unread_count }}</span>
    </div>

    <!-- Content -->
    <div class="flex-1 min-w-0">
      <p class="text-[13px] font-semibold text-on-surface truncate">{{ conv.title }}</p>
      <p class="text-[11px] text-on-surface-variant truncate mt-0.5">{{ conv.last_message_preview ?? 'No messages yet' }}</p>
    </div>

    <!-- Actions -->
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
        <button class="conv-action-item" @click.stop="$emit('rename', conv)">
          <el-icon :size="14"><Edit /></el-icon>
          <span>Rename</span>
        </button>
        <button class="conv-action-item" @click.stop="$emit('togglePin', conv)">
          <el-icon :size="14"><component :is="conv.is_pinned ? Aim : Promotion" /></el-icon>
          <span>{{ conv.is_pinned ? 'Unpin' : 'Pin' }}</span>
        </button>
        <button class="conv-action-item" @click.stop="$emit('toggleArchive', conv)">
          <el-icon :size="14"><component :is="conv.is_archived ? FolderOpened : Folder" /></el-icon>
          <span>{{ conv.is_archived ? 'Unarchive' : 'Archive' }}</span>
        </button>
      </div>
    </el-popover>
  </div>
</template>

<script setup lang="ts">
import { ChatDotRound, MoreFilled, Edit, Aim, Promotion, Folder, FolderOpened } from '@element-plus/icons-vue'
import type { ConversationListItem } from '@/types/conversation'

defineProps<{ conv: ConversationListItem }>()
defineEmits<{
  rename: [conv: ConversationListItem]
  togglePin: [conv: ConversationListItem]
  toggleArchive: [conv: ConversationListItem]
}>()
</script>
