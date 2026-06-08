<template>
  <div class="px-4 py-3 bg-amber-50 border-t-2 border-amber-300">
    <!-- Header -->
    <div class="flex items-center gap-2 mb-2">
      <el-icon :size="16" class="text-amber-600"><Warning /></el-icon>
      <span class="text-[13px] font-semibold text-amber-800">{{ t('approvalOverlay.title') }}</span>
    </div>

    <!-- Action + Detail -->
    <div class="mb-3 px-3 py-2 bg-white rounded-lg border border-amber-200">
      <p class="text-[11px] font-semibold text-amber-700 uppercase tracking-wide mb-1">{{ approval.action }}</p>
      <p class="text-[12px] text-on-surface whitespace-pre-wrap">{{ approval.detail }}</p>
    </div>

    <!-- Reject reason input -->
    <div v-if="showRejectInput" class="mb-3">
      <input
        ref="reasonInput"
        v-model="rejectReason"
        type="text"
        :placeholder="t('approval.rejectReasonPlaceholder')"
        class="w-full px-3 py-1.5 text-[12px] border border-red-200 rounded-lg focus:outline-none focus:border-red-400 bg-white"
        @keydown.enter="confirmReject"
        @keydown.escape="showRejectInput = false"
      />
    </div>

    <!-- Buttons -->
    <div class="flex items-center gap-2">
      <button
        class="px-4 py-1.5 text-[12px] font-medium rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors cursor-pointer"
        @click="$emit('approve')"
      >
        {{ t('approval.approveButton') }}
      </button>
      <button
        v-if="!showRejectInput"
        class="px-4 py-1.5 text-[12px] font-medium rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors cursor-pointer"
        @click="showRejectInput = true"
      >
        {{ t('approval.rejectButton') }}
      </button>
      <button
        v-else
        class="px-4 py-1.5 text-[12px] font-medium rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors cursor-pointer"
        @click="confirmReject"
      >
        {{ t('approval.confirmReject') }}
      </button>
      <span class="text-[10px] text-amber-600 ml-auto">{{ t('approval.keyboardHint') }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { Warning } from '@element-plus/icons-vue'

const { t } = useI18n()

const props = defineProps<{
  approval: { messageId: string; blockId: string; action: string; detail: string }
}>()

const emit = defineEmits<{
  approve: []
  reject: [reason?: string]
}>()

const showRejectInput = ref(false)
const rejectReason = ref('')
const reasonInput = ref<HTMLInputElement | null>(null)

function confirmReject() {
  emit('reject', rejectReason.value || undefined)
}

function onKeydown(e: KeyboardEvent) {
  if (showRejectInput.value) return
  if (e.key === 'y' || e.key === 'Y') {
    e.preventDefault()
    emit('approve')
  } else if (e.key === 'n' || e.key === 'N') {
    e.preventDefault()
    showRejectInput.value = true
    nextTick(() => reasonInput.value?.focus())
  }
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>
