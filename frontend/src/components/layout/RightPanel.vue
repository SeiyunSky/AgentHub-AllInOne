<template>
  <PanelContainer
    :title="panelTitle"
    :icon="panelIcon"
    :variant="panelVariant"
    :status="workflowStatus"
    :status-dot="activeTab === 'workflow'"
  >
    <!-- 头部右侧:Preview 模式专属操作(View / Edit / Close) -->
    <template #headerActions>
      <template v-if="activeTab === 'preview'">
        <div class="flex items-center gap-1 px-1 py-0.5 rounded-lg bg-surface-container">
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

    <!-- 主体:左侧内容 + 右侧竖向 tabs -->
    <div class="h-full flex">
      <!-- 内容区 -->
      <div class="flex-1 min-w-0 overflow-hidden">
        <WorkflowView v-if="activeTab === 'workflow'" />
        <SandboxFilesView v-else-if="activeTab === 'files'" />
        <DeploymentsView v-else-if="activeTab === 'deployments'" />
        <ArtifactRouter v-else :mode="previewMode" />
      </div>

      <!-- 竖向 tab 侧栏(放右边,块内容靠左) -->
      <nav class="shrink-0 w-12 border-l border-outline-variant bg-surface-container-low/50 flex flex-col py-2 gap-1">
        <button
          v-for="t in tabs"
          :key="t.id"
          :title="t.label"
          :disabled="t.disabled"
          class="vertical-tab"
          :class="[
            activeTab === t.id ? 'vertical-tab-active' : 'vertical-tab-idle',
            t.disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer',
          ]"
          @click="!t.disabled && uiStore.setRightPanelTab(t.id)"
        >
          <el-icon :size="16">
            <component :is="t.icon" />
          </el-icon>
          <span class="text-[9px] mt-1 leading-none">{{ t.label }}</span>
          <!-- badge: 数量 -->
          <span v-if="t.badge"
                class="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full bg-brand text-white text-[9px] font-bold flex items-center justify-center"
          >
            {{ t.badge }}
          </span>
        </button>
      </nav>
    </div>


  </PanelContainer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useUIStore } from '@/stores/ui'
import { useArtifactPreview } from '@/composables/useArtifactPreview'
import { useChatStore } from '@/stores/chat'
import { useConversationsStore } from '@/stores/conversations'
import { useDeploymentsStore } from '@/stores/deployments'
import PanelContainer from './PanelContainer.vue'
import WorkflowView from './WorkflowView.vue'
import SandboxFilesView from './SandboxFilesView.vue'
import DeploymentsView from './DeploymentsView.vue'
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
  Promotion,
} from '@element-plus/icons-vue'

const uiStore = useUIStore()
const chatStore = useChatStore()
const conversationsStore = useConversationsStore()
const deploymentsStore = useDeploymentsStore()
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

const deploymentCount = computed(() => deploymentsStore.getCount(convId.value))

// 4 个 tab,Preview 在选中 artifact 时可用
const tabs = computed(() => [
  { id: 'workflow' as const, label: 'Workflow', icon: Share, disabled: false, badge: 0 },
  { id: 'files' as const, label: 'Files', icon: FolderOpened, disabled: false, badge: 0 },
  {
    id: 'deployments' as const,
    label: 'Deploy',
    icon: Promotion,
    disabled: false,
    badge: deploymentCount.value,
  },
  {
    id: 'preview' as const,
    label: 'Preview',
    icon: View,
    disabled: !activeArtifact.value,
    badge: 0,
  },
])

const panelTitle = computed(() => {
  if (activeTab.value === 'preview') return activeArtifact.value?.item.name ?? 'Preview'
  if (activeTab.value === 'files') return 'Files'
  if (activeTab.value === 'deployments') return 'Deployments'
  return 'Workflow'
})

const panelIcon = computed(() => {
  if (activeTab.value === 'preview') return View
  if (activeTab.value === 'files') return FolderOpened
  if (activeTab.value === 'deployments') return Promotion
  return Share
})

const panelVariant = computed(() => {
  if (activeTab.value === 'preview') return 'neutral'
  if (activeTab.value === 'files') return 'neutral'
  if (activeTab.value === 'deployments') return 'success'
  return 'brand'
})
</script>

<style scoped>
.vertical-tab {
  position: relative;
  width: 40px;
  height: 52px;
  margin: 0 auto;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
  border: none;
  background: transparent;
  padding: 0;
}
.vertical-tab-idle {
  color: var(--color-on-surface-variant);
}
.vertical-tab-idle:hover {
  background: var(--color-surface-container);
  color: var(--color-on-surface);
}
.vertical-tab-active {
  background: var(--color-brand);
  color: white;
}
</style>
