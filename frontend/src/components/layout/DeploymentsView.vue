<template>
  <div class="h-full flex flex-col overflow-hidden">
    <!-- 空态 -->
    <div v-if="deployments.length === 0" class="flex-1 flex flex-col items-center justify-center gap-4 px-6 text-center">
      <div class="w-16 h-16 rounded-2xl flex items-center justify-center"
           style="background: linear-gradient(135deg, rgba(16,185,129,0.12), rgba(6,182,212,0.08));">
        <el-icon :size="28" class="text-emerald-500/50"><Promotion /></el-icon>
      </div>
      <div>
        <p class="text-[13px] font-semibold text-on-surface-variant">{{ t('deployments.emptyTitle') }}</p>
        <p class="text-[11px] text-on-surface-variant/60 mt-1">{{ t('deployments.emptyDesc') }}</p>
      </div>
    </div>

    <!-- 活跃部署的 iframe 预览(占大部分空间) -->
    <div v-else-if="active" class="flex-1 flex flex-col overflow-hidden">
      <!-- URL 工具栏 -->
      <div class="shrink-0 px-3 py-2 border-b border-outline-variant flex items-center gap-2 bg-surface-container-low">
        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" :title="t('deployments.running')"></span>
        <span class="text-[11px] text-on-surface-variant shrink-0">{{ t('deployments.urlLabel') }}</span>
        <code class="text-[11px] text-on-surface bg-white px-2 py-1 rounded font-mono truncate flex-1">{{ fullUrl(active.url) }}</code>
        <button
          class="text-[11px] text-brand hover:text-brand-dark hover:bg-brand-light/30 transition-colors px-2 py-1 rounded cursor-pointer"
          :title="t('deployments.copyUrl')"
          @click="copyUrl(active.url)"
        >
          {{ copied ? t('deploymentsExtra.copied') : t('deployments.copyUrl') }}
        </button>
        <a
          :href="active.url"
          target="_blank"
          class="text-[11px] text-brand hover:text-brand-dark hover:bg-brand-light/30 transition-colors px-2 py-1 rounded cursor-pointer flex items-center gap-1"
          :title="t('deployments.openInTab')"
        >
          <el-icon :size="11"><Promotion /></el-icon>
          {{ t('deployments.openInTab') }}
        </a>
        <button
          class="text-[11px] text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors px-2 py-1 rounded cursor-pointer"
          :title="t('deployments.refresh')"
          @click="refreshIframe"
        >
          <el-icon :size="11"><Refresh /></el-icon>
        </button>
      </div>

      <!-- iframe 预览 -->
      <div class="flex-1 overflow-hidden bg-white">
        <iframe
          :key="iframeKey"
          :src="active.url"
          class="w-full h-full border-0"
          sandbox="allow-scripts allow-forms allow-popups allow-same-origin"
        />
      </div>

      <!-- 部署历史(下方折叠) -->
      <div v-if="deployments.length > 1" class="shrink-0 border-t border-outline-variant">
        <div class="px-3 py-2 cursor-pointer hover:bg-surface-container-low flex items-center gap-2 select-none"
             @click="historyExpanded = !historyExpanded">
          <el-icon :size="11" class="transition-transform" :class="{ 'rotate-90': historyExpanded }"><ArrowRight /></el-icon>
          <span class="text-[11px] font-medium text-on-surface-variant">{{ t('deployments.historyLabel') }} ({{ deployments.length }})</span>
        </div>
        <div v-if="historyExpanded" class="max-h-40 overflow-y-auto custom-scrollbar bg-surface-container-low/40">
          <div v-for="d in [...deployments].reverse()" :key="d.id"
               class="px-3 py-2 border-t border-outline-variant/40 first:border-t-0 flex items-center gap-2">
            <span :class="statusDotClass(d)" class="w-1.5 h-1.5 rounded-full shrink-0"></span>
            <code class="text-[10px] font-mono text-on-surface-variant truncate flex-1">{{ d.entryPoint }}</code>
            <span class="text-[10px] text-on-surface-variant/60 shrink-0 font-mono">{{ formatTime(d.startedAt) }}</span>
            <span v-if="d.active" class="text-[9px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-bold shrink-0">{{ t('deploymentsExtra.activeStatus') }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 没有 active(都失败了)显示最后一次的错误 + 历史列表 -->
    <div v-else class="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-2">
      <div class="rounded-xl border border-red-200 bg-red-50/50 p-4">
        <div class="flex items-center gap-2 mb-2">
          <el-icon :size="14" class="text-red-500"><CircleCloseFilled /></el-icon>
          <span class="text-[12px] font-semibold text-red-700">{{ t('deployments.latestFailed') }}</span>
        </div>
        <p class="text-[11px] text-red-600 mb-2">{{ deployments[deployments.length - 1].errorMessage ?? t('deployments.unknownError') }}</p>
        <pre v-if="deployments[deployments.length - 1].logs"
             class="text-[10px] font-mono bg-white border border-red-100 rounded p-2 overflow-x-auto max-h-40 overflow-y-auto whitespace-pre-wrap">{{ deployments[deployments.length - 1].logs }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Promotion, Refresh, ArrowRight, CircleCloseFilled } from '@element-plus/icons-vue'
import { useDeploymentsStore } from '@/stores/deployments'
import { useConversationsStore } from '@/stores/conversations'
import type { Deployment } from '@/stores/deployments'
import { copyToClipboard } from '@/utils/clipboard'

const { t } = useI18n()

const deploymentsStore = useDeploymentsStore()
const conversationsStore = useConversationsStore()

const convId = computed(() => conversationsStore.currentId ?? '')
const deployments = computed(() => deploymentsStore.getDeployments(convId.value))
const active = computed(() => deploymentsStore.getActive(convId.value))

const historyExpanded = ref(false)
const copied = ref(false)
const iframeKey = ref(0)

function fullUrl(rel: string): string {
  // rel 是 /preview/{conv_id}/,显示带 host 让用户知道完整 URL
  return `${window.location.origin}${rel}`
}

async function copyUrl(rel: string) {
  await copyToClipboard(fullUrl(rel))
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}

function refreshIframe() {
  iframeKey.value += 1
}

function statusDotClass(d: Deployment): string {
  if (d.status === 'error') return 'bg-red-400'
  if (d.active) return 'bg-emerald-400 animate-pulse'
  return 'bg-on-surface-variant/30'
}

function formatTime(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
</script>
