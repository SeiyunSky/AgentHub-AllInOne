<template>
  <aside class="fixed left-0 top-0 h-full z-40 flex">
    <!-- Navigation Rail - always visible -->
    <NavRail />

    <!-- Secondary List Panel - collapses via width -->
    <div
      class="h-full overflow-hidden transition-all duration-300"
      style="transition-timing-function: cubic-bezier(0.16, 1, 0.3, 1);"
      :style="{ width: uiStore.sidebarCollapsed ? '0px' : '240px' }"
    >
      <ListPanel />
    </div>

    <!-- Collapse Button -->
    <button
      class="absolute top-1/2 z-50 rounded-xl w-7 h-7 flex items-center justify-center bg-white border border-outline-variant shadow-card hover:bg-surface-container hover:border-brand hover:shadow-glow transition-all duration-300 text-on-surface-variant hover:text-brand"
      :style="{ left: uiStore.sidebarCollapsed ? '68px' : '308px', transform: 'translate(-50%, -50%)' }"
      @click="uiStore.toggleSidebar"
    >
      <el-icon :size="14">
        <ArrowLeft v-if="!uiStore.sidebarCollapsed" />
        <ArrowRight v-else />
      </el-icon>
    </button>
  </aside>
</template>

<script setup lang="ts">
import { useUIStore } from '@/stores/ui'
import NavRail from './NavRail.vue'
import ListPanel from './ListPanel.vue'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'

const uiStore = useUIStore()
</script>