<template>
  <PanelContainer
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
import PanelContainer from './PanelContainer.vue'
import WorkflowView from './WorkflowView.vue'
import { Share, Plus, ZoomIn, Aim, Operation } from '@element-plus/icons-vue'
</script>