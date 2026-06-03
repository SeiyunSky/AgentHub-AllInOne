<template>
  <div class="relative flex items-center gap-3">
    <!-- Agent avatars container (fixed size, flex-wrap layout like WeChat) -->
    <div class="relative shrink-0 w-10 h-10 rounded-lg overflow-hidden">
      <div
        class="w-full h-full p-[3%] flex flex-wrap justify-center content-center items-center gap-[3%]"
      >
        <div
          v-for="(agent, idx) in displayAgents"
          :key="agent.id"
          class="flex items-center justify-center overflow-hidden rounded-[20%]"
          :class="avatarClass"
          :style="avatarStyle(idx)"
        >
          <img
            v-if="agent.avatar"
            :src="agent.avatar"
            :alt="agent.name"
            class="w-full h-full object-cover"
          />
          <span v-else class="text-[10px] font-bold" :class="textClass(idx)">{{ getInitials(agent.name) }}</span>
        </div>
      </div>
      <span
        v-if="conv.unread_count"
        class="absolute -top-1 -right-1 min-w-[16px] h-4 bg-brand text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1 shadow-sm ring-2 ring-white"
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
import { MoreFilled, Edit, Aim, Promotion, Folder, FolderOpened, Delete } from '@element-plus/icons-vue'
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

// 最多展示9个agent头像
const displayAgents = computed(() => props.conv.agents?.slice(0, 9) ?? [])

// 头像颜色循环
const avatarColors = ['brand', 'warning', 'success', 'error'] as const

// 根据头像数量动态计算尺寸类名
const avatarClass = computed(() => {
  const count = displayAgents.value.length
  if (count === 1) {
    return 'w-full h-full'
  } else if (count >= 2 && count <= 4) {
    return 'w-[47%] h-[47%]'
  } else {
    return 'w-[31%] h-[31%]'
  }
})

// 头像背景色
function avatarStyle(idx: number) {
  const color = avatarColors[idx % 4]
  const bgMap: Record<string, string> = {
    brand: 'linear-gradient(to bottom right, var(--color-brand-light), var(--color-brand-subtle))',
    warning: 'linear-gradient(to bottom right, var(--color-warning-light), #fde68a)',
    success: 'linear-gradient(to bottom right, var(--color-success-light), #d1fae5)',
    error: 'linear-gradient(to bottom right, var(--color-error-light), #fecaca)',
  }
  return { background: bgMap[color] }
}

// 头像文字色
function textClass(idx: number) {
  const color = avatarColors[idx % 4]
  return {
    'text-brand': color === 'brand',
    'text-amber-600': color === 'warning',
    'text-success': color === 'success',
    'text-error': color === 'error',
  }
}

// 获取首字母
function getInitials(name: string) {
  const words = name.trim().split(/\s+/)
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase()
  return name[0]?.toUpperCase() ?? ''
}

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
