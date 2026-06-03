<template>
  <PanelContainer
    :title="panelTitle"
    :icon="panelIcon"
    :variant="panelVariant"
    :status="workflowStatus"
    :status-dot="activeTab === 'workflow'"
  >
    <!-- 三 Tab 同级内容 -->
    <WorkflowView v-if="activeTab === 'workflow'" />
    <SandboxFilesView v-else-if="activeTab === 'files'" />
    <ArtifactRouter v-else :mode="previewMode" />

    <!-- 头部 Tab 切换 chips + 上下文按钮 -->
    <template #headerActions>
      <div class="flex items-center gap-1 px-1 py-0.5 rounded-lg bg-surface-container">
        <button
          class="px-2 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1"
          :class="activeTab === 'workflow' ? 'bg-brand text-white' : 'text-on-surface-variant hover:text-on-surface'"
          @click="uiStore.setRightPanelTab('workflow')"
        >
          <el-icon :size="12"><Share /></el-icon>
          Workflow
        </button>
        <button
          class="px-2 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1"
          :class="activeTab === 'files' ? 'bg-brand text-white' : 'text-on-surface-variant hover:text-on-surface'"
          @click="uiStore.setRightPanelTab('files')"
        >
          <el-icon :size="12"><FolderOpened /></el-icon>
          Files
        </button>
        <button
          class="px-2 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="activeTab === 'preview' ? 'bg-brand text-white' : 'text-on-surface-variant hover:text-on-surface'"
          :disabled="!activeArtifact"
          :title="activeArtifact ? 'Preview the selected artifact' : 'Select a file or artifact to preview'"
          @click="activeArtifact && uiStore.setRightPanelTab('preview')"
        >
          <el-icon :size="12"><View /></el-icon>
          Preview
        </button>
      </div>

      <!-- Preview Tab 专属:Preview/Edit 模式切换 + 关闭 -->
      <template v-if="activeTab === 'preview'">
        <div class="flex items-center gap-1 px-1 py-0.5 rounded-lg bg-surface-container ml-2">
          <button
            class="px-2 py-1 rounded text-[11px] font-medium transition-colors"
            :class="previewMode === 'preview' ? 'bg-brand text-white' : 'text-on-surface-variant hover:text-on-surface'"
            @click="setMode('preview')"
          >
            <el-icon :size="12" class="mr-1"><View /></el-icon>
            View
          </button>
          <button
            class="px-2 py-1 rounded text-[11px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            :class="previewMode === 'edit' ? 'bg-brand text-white' : 'text-on-surface-variant hover:text-on-surface'"
            :disabled="!isEditable"
            @click="setMode('edit')"
          >
            <el-icon :size="12" class="mr-1"><Edit /></el-icon>
            Edit
          </button>
        </div>
        <button
          class="w-7 h-7 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
          title="Close preview (back to last tab)"
          @click="closeArtifact"
        >
          <el-icon :size="14"><Close /></el-icon>
        </button>
      </template>
    </template>

    <!-- Workflow Tab 专属:工具栏(放大缩小等) -->
    <template v-if="activeTab === 'workflow'" #toolbar>
      <button class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors">
        <el-icon :size="16"><Plus /></el-icon>
      </button>
      <div class="w-px h-4 bg-outline-variant"></div>
      <button class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors">
        <el-icon :size="16"><ZoomIn /></el-icon>
      </button>
      <button class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors">
        <el-icon :size="16"><Aim /></el-icon>
      </button>
      <div class="w-px h-4 bg-outline-variant"></div>
      <button class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors">
        <el-icon :size="16"><Operation /></el-icon>
      </button>
    </template>
  </PanelContainer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useUIStore } from '@/stores/ui'
import { useArtifactPreview } from '@/composables/useArtifactPreview'
import { useChatStore } from '@/stores/chat'
import { useConversationsStore } from '@/stores/conversations'
import PanelContainer from './PanelContainer.vue'
import WorkflowView from './WorkflowView.vue'
import SandboxFilesView from './SandboxFilesView.vue'
import ArtifactRouter from '@/components/chat/artifacts/ArtifactRouter.vue'
import {
  Share,
  Plus,
  ZoomIn,
  Aim,
  Operation,
  View,
  Edit,
  Close,
  FolderOpened,
} from '@element-plus/icons-vue'

const uiStore = useUIStore()
const chatStore = useChatStore()
const conversationsStore = useConversationsStore()
const { activeArtifact, closeArtifact, setMode } = useArtifactPreview()

const activeTab = computed(() => uiStore.rightPanelActiveTab)
const previewMode = computed(() => uiStore.activeArtifact?.mode ?? 'preview')
const convId = computed(() => conversationsStore.currentId ?? '')

const workflowStatus = computed(() =>
  chatStore.isStreamingFor(convId.value) ? 'Running' : 'Idle'
)

// Edit 模式可用 = 有 filePath(老路径)或 convId+path(沙箱)
const isEditable = computed(() => {
  const item = activeArtifact.value?.item
  return !!item && (!!item.filePath || (!!item.convId && !!item.path))
})

const panelTitle = computed(() => {
  if (activeTab.value === 'preview') return activeArtifact.value?.item.name ?? 'Preview'
  if (activeTab.value === 'files') return 'Files'
  return 'Workflow'
})

const panelIcon = computed(() => {
  if (activeTab.value === 'preview') return View
  if (activeTab.value === 'files') return FolderOpened
  return Share
})

const panelVariant = computed(() => {
  if (activeTab.value === 'preview') return 'neutral'
  if (activeTab.value === 'files') return 'neutral'
  return 'brand'
})
</script>
