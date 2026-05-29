<template>
  <!-- Preview mode -->
  <PanelContainer
    v-if="uiStore.rightPanelActiveTab === 'preview'"
    :title="activeArtifact?.item.name ?? 'Preview'"
    :icon="View"
    variant="neutral"
    :status-dot="false"
  >
    <ArtifactRouter :mode="previewMode" />

    <template #toolbar>
      <!-- Preview/Code toggle -->
      <div class="flex items-center gap-1 px-1 py-0.5 rounded-lg bg-surface-container">
        <button
          class="px-2 py-1 rounded text-[11px] font-medium transition-colors"
          :class="previewMode === 'preview' ? 'bg-brand text-white' : 'text-on-surface-variant hover:text-on-surface'"
          @click="setMode('preview')"
        >
          <el-icon :size="12" class="mr-1"><View /></el-icon>
          Preview
        </button>
        <button
          class="px-2 py-1 rounded text-[11px] font-medium transition-colors"
          :class="previewMode === 'code' ? 'bg-brand text-white' : 'text-on-surface-variant hover:text-on-surface'"
          @click="setMode('code')"
        >
          <el-icon :size="12" class="mr-1"><CopyDocument /></el-icon>
          Code
        </button>
      </div>
      <div class="w-px h-4 bg-outline-variant"></div>
      <button
        class="w-7 h-7 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
        @click="closeArtifact"
      >
        <el-icon :size="14"><Close /></el-icon>
      </button>
    </template>
  </PanelContainer>

  <!-- Workflow mode (default) -->
  <PanelContainer
    v-else
    title="Workflow"
    status="Running"
    :icon="Share"
    variant="brand"
  >
    <WorkflowView />

    <template #toolbar>
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
import PanelContainer from './PanelContainer.vue'
import WorkflowView from './WorkflowView.vue'
import ArtifactRouter from '@/components/chat/artifacts/ArtifactRouter.vue'
import { Share, Plus, ZoomIn, Aim, Operation, View, CopyDocument, Close } from '@element-plus/icons-vue'

const uiStore = useUIStore()
const { activeArtifact, closeArtifact, setMode } = useArtifactPreview()

const previewMode = computed(() => uiStore.activeArtifact?.mode ?? 'preview')
</script>