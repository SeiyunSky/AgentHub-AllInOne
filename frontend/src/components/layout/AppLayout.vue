<template>
  <div class="fixed inset-0 flex bg-surface text-on-surface overflow-hidden">
    <!-- Left Sidebar -->
    <LeftPanel />

    <!-- NavRail expand button — rendered at root level so z-index is independent -->
    <button
      v-if="uiStore.navRailCollapsed"
      class="fixed left-0 top-1/2 -translate-y-1/2 z-[100] w-5 h-14 flex items-center justify-center bg-white border border-l-0 border-outline-variant shadow-card hover:bg-surface-container hover:border-brand hover:text-brand rounded-r-xl text-on-surface-variant transition-all duration-200"
      @click="uiStore.toggleNavRail"
      title="Expand sidebar"
    >
      <el-icon :size="12"><ArrowRight /></el-icon>
    </button>

    <!-- Main Content Area — driven by router -->
    <div
      id="main-content"
      class="flex-1 flex flex-col transition-all duration-300 overflow-hidden"
      :style="{ marginLeft: `${uiStore.sidebarWidth}px` }"
    >
      <main class="flex-1 overflow-hidden">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useUIStore } from '@/stores/ui'
import { ArrowRight } from '@element-plus/icons-vue'
import LeftPanel from './LeftPanel.vue'

const uiStore = useUIStore()
</script>
