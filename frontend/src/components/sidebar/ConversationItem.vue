<template>
  <div class="relative flex items-center gap-3">
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
      <div class="flex items-center gap-1">
        <p class="text-[14px] font-semibold text-on-surface truncate flex-1 min-w-0">{{ conv.title }}</p>
        <span class="text-[11px] text-on-surface-variant/60 whitespace-nowrap group-hover:opacity-0 transition-opacity duration-150 select-none shrink-0">{{ lastMessageTime }}</span>
      </div>
      <p class="text-[11px] text-on-surface-variant truncate mt-0.5 pr-6">{{ conv.last_message_preview ?? 'No messages yet' }}</p>
    </div>

    <!-- Actions button (absolute, overlays time on hover) -->
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
          class="absolute right-0 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-neutral-200/60 transition-all cursor-pointer"
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
        <button class="conv-action-item !text-error hover:!bg-error-light" @click.stop="handleDelete">
          <el-icon :size="14"><Delete /></el-icon>
          <span>Delete</span>
        </button>
      </div>
    </el-popover>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { ChatDotRound, MoreFilled, Edit, Aim, Promotion, Folder, FolderOpened, Delete } from '@element-plus/icons-vue'
import { useConversationsStore } from '@/stores/conversations'
import { useRouter } from 'vue-router'
import type { ConversationListItem } from '@/types/conversation'

const props = defineProps<{ conv: ConversationListItem }>()
const emit = defineEmits<{
  rename: [conv: ConversationListItem]
  togglePin: [conv: ConversationListItem]
  toggleArchive: [conv: ConversationListItem]
}>()

const conversationsStore = useConversationsStore()
const router = useRouter()

async function handleDelete() {
  try {
    await ElMessageBox.confirm('确认删除该会话？此操作不可恢复。', '删除会话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
      customStyle: { borderRadius: '16px' },
    })
  } catch {
    return
  }
  try {
    await conversationsStore.remove(props.conv.id)
    if (router.currentRoute.value.params.conversationId === props.conv.id) {
      router.push({ name: 'chat' })
    }
  } catch {
    ElMessage({ message: '删除失败，请重试', type: 'error', duration: 2000, plain: true })
  }
}

const lastMessageTime = computed(() => {
  const raw = props.conv.last_message_at ?? props.conv.updated_at
  if (!raw) return ''
  const date = new Date(raw)
  const now = new Date()
  const isToday = date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth()
    && date.getDate() === now.getDate()
  if (isToday) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  }
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
})
</script>
