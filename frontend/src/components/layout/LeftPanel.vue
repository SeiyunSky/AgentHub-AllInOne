<template>
  <aside class="fixed left-0 top-0 h-full z-40 flex">
    <!-- Navigation Rail - collapses via width -->
    <div
      class="h-full overflow-hidden transition-all duration-300"
      style="transition-timing-function: cubic-bezier(0.16, 1, 0.3, 1);"
      :style="{ width: uiStore.navRailCollapsed ? '0px' : '160px' }"
    >
      <NavRail />
    </div>

    <!-- Secondary List Panel - collapses via width -->
    <div
      class="h-full overflow-hidden transition-all duration-300"
      style="transition-timing-function: cubic-bezier(0.16, 1, 0.3, 1);"
      :style="{ width: (uiStore.navRailCollapsed || uiStore.sidebarCollapsed) ? '0px' : '280px' }"
    >
      <ListPanel />
    </div>

    <!-- Collapse toggle button (List Panel) — only visible when NavRail is open -->
    <button
      v-if="!uiStore.navRailCollapsed"
      class="absolute top-1/2 z-50 rounded-xl w-7 h-7 flex items-center justify-center bg-white border border-outline-variant shadow-card hover:bg-surface-container hover:border-brand hover:shadow-glow transition-all duration-300 text-on-surface-variant hover:text-brand"
      :style="{ left: uiStore.sidebarCollapsed ? '160px' : '440px', transform: 'translate(-50%, -50%)' }"
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
