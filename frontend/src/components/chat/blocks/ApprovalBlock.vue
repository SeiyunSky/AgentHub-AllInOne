<template>
  <CollapsibleBlock
    :label="action"
    :icon="icon"
    :variant="variant"
    :badge="badge"
    :default-expanded="true"
  >
    <div class="px-3 py-2 space-y-2">
      <!-- 结构化详情(create_file/edit_file 显示路径+大小+折叠内容,其他工具兜底原文) -->
      <ApprovalDetail :action="action" :detail="detail" />

      <!-- Status indicators -->
      <div v-if="status === 'approved'" class="flex items-center gap-1.5 text-[11px] text-emerald-600">
        <el-icon :size="12"><CircleCheck /></el-icon>
        <span>Approved{{ decidedAt ? ' at ' + formatTime(decidedAt) : '' }}</span>
      </div>
      <div v-else-if="status === 'rejected'" class="space-y-1">
        <div class="flex items-center gap-1.5 text-[11px] text-red-600">
          <el-icon :size="12"><CircleClose /></el-icon>
          <span>Rejected{{ decidedAt ? ' at ' + formatTime(decidedAt) : '' }}</span>
        </div>
        <p v-if="rejectReason" class="text-[11px] text-red-500 pl-5">{{ rejectReason }}</p>
      </div>

      <!-- Pending: approval buttons -->
      <div v-else class="space-y-2">
        <div class="flex items-center gap-1.5 text-[11px] text-amber-600">
          <el-icon class="animate-pulse" :size="12"><Warning /></el-icon>
          <span>Waiting for approval...</span>
        </div>

        <!-- Reject reason input -->
        <div v-if="showRejectInput">
          <input
            ref="reasonInput"
            v-model="rejectReason"
            type="text"
            placeholder="Reason for rejection (optional)"
            class="w-full px-3 py-1.5 text-[12px] border border-red-200 rounded-lg focus:outline-none focus:border-red-400 bg-white"
            @keydown.enter="confirmReject"
            @keydown.escape="showRejectInput = false"
          />
        </div>

        <div class="flex items-center gap-2">
          <button
            class="px-4 py-1.5 text-[12px] font-medium rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors cursor-pointer"
            @click="handleApprove"
          >
            Approve (Y)
          </button>
          <button
            v-if="!showRejectInput"
            class="px-4 py-1.5 text-[12px] font-medium rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors cursor-pointer"
            @click="showRejectInput = true; nextTick(() => reasonInput?.focus())"
          >
            Reject (N)
          </button>
          <button
            v-else
            class="px-4 py-1.5 text-[12px] font-medium rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors cursor-pointer"
            @click="confirmReject"
          >
            Confirm
          </button>
          <span class="text-[10px] text-amber-600 ml-auto">Press Y / N</span>
        </div>
      </div>
    </div>
  </CollapsibleBlock>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, nextTick } from 'vue'
import { Warning, CircleCheck, CircleClose, Lock } from '@element-plus/icons-vue'
import CollapsibleBlock from './CollapsibleBlock.vue'
import ApprovalDetail from './ApprovalDetail.vue'
import { useChatStore } from '@/stores/chat'
import { useConversationsStore } from '@/stores/conversations'
import { http } from '@/api/http'

const props = defineProps<{
  messageId: string
  blockId: string
  action: string
  detail: string
  status: 'pending' | 'approved' | 'rejected'
  decidedAt?: string
  rejectReason?: string
}>()

const conversationsStore = useConversationsStore()
const chatStore = useChatStore()

const showRejectInput = ref(false)
const rejectReason = ref('')
const reasonInput = ref<HTMLInputElement | null>(null)

async function postDecision(decision: 'approve' | 'reject', reason?: string) {
  const convId = conversationsStore.currentId
  try {
    await http.post(`/approvals/${props.blockId}/decide`, { decision, reason: reason ?? null })
    chatStore.resolveApproval(
      convId ?? '',
      props.messageId,
      props.blockId,
      decision === 'approve' ? 'approved' : 'rejected',
    )
  } catch (e) {
    console.error('[Approval] post decision failed', e)
  }
}

const icon = computed(() => {
  if (props.status === 'approved') return CircleCheck
  if (props.status === 'rejected') return CircleClose
  return Lock
})

const variant = computed(() => {
  if (props.status === 'approved') return 'success'
  if (props.status === 'rejected') return 'error'
  return 'approval'
})

const badge = computed(() => {
  if (props.status === 'approved') return 'approved'
  if (props.status === 'rejected') return 'rejected'
  return 'pending'
})

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString()
}

function handleApprove() {
  postDecision('approve')
}

function confirmReject() {
  postDecision('reject', rejectReason.value || undefined)
  showRejectInput.value = false
}

function onKeydown(e: KeyboardEvent) {
  if (props.status !== 'pending') return
  if (showRejectInput.value) return
  // 焦点在输入类元素时不拦截（用户正在打字，不应触发审批快捷键）
  const active = document.activeElement as HTMLElement | null
  const tag = active?.tagName?.toLowerCase()
  if (tag === 'input' || tag === 'textarea') return
  if (active?.isContentEditable) return
  // Monaco / CodeMirror 等代码编辑器：焦点在内部 textarea 或带特定 class 的容器
  if (active?.closest('.monaco-editor, .cm-editor, [contenteditable="true"]')) return
  if (e.key === 'y' || e.key === 'Y') {
    e.preventDefault()
    handleApprove()
  } else if (e.key === 'n' || e.key === 'N') {
    e.preventDefault()
    showRejectInput.value = true
    nextTick(() => reasonInput.value?.focus())
  }
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>
