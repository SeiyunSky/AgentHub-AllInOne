<template>
  <section class="flex flex-col flex-1 min-w-0 bg-surface relative overflow-hidden h-full">
    <!-- Tab Bar -->
    <div class="flex items-center gap-1 bg-white border-b border-outline-variant h-11 shrink-0 px-3 py-1.5">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="flex items-center px-3.5 py-1.5 gap-2 cursor-pointer rounded-lg transition-all duration-200 text-[12px] font-medium"
        :class="[
          uiStore.rightPanelActiveTab === tab.id
            ? 'bg-brand-light text-brand border border-brand/20'
            : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface border border-transparent'
        ]"
        @click="uiStore.rightPanelActiveTab = tab.id"
      >
        <el-icon :size="15">
          <component :is="tab.icon" />
        </el-icon>
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <!-- Tab Content -->
    <div class="flex-1 overflow-hidden">
      <WorkflowView v-if="uiStore.rightPanelActiveTab === 'workflow'" />
      <PreviewView v-else />
    </div>

    <!-- Floating Toolbar -->
    <div class="absolute bottom-5 right-5 glass-panel border border-outline-variant rounded-xl shadow-float p-1.5 flex items-center gap-1 z-30">
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
    </div>
  </section>
</template>

<script setup lang="ts">
import { useUIStore } from '@/stores/ui'
import WorkflowView from './WorkflowView.vue'
import PreviewView from './PreviewView.vue'
import { Share, View, Plus, ZoomIn, Aim, Operation } from '@element-plus/icons-vue'

const uiStore = useUIStore()

const tabs = [
  { id: 'workflow', label: 'Workflow', icon: Share },
  { id: 'preview', label: 'Preview', icon: View },
] as const
</script>