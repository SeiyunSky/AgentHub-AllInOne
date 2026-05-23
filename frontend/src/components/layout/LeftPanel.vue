<template>
  <aside
    class="fixed left-0 top-0 h-full z-40 flex transition-transform duration-300"
    :class="{ '-translate-x-full': uiStore.sidebarCollapsed }"
    style="transition-timing-function: cubic-bezier(0.16, 1, 0.3, 1);"
  >
    <!-- Navigation Rail -->
    <NavRail />

    <!-- Secondary List Panel -->
    <ListPanel />

    <!-- Collapse Button -->
    <button
      class="absolute top-1/2 right-0 translate-x-1/2 -translate-y-1/2 bg-white border border-outline-variant shadow-card z-50 rounded-xl w-7 h-7 flex items-center justify-center hover:bg-surface-container hover:border-brand hover:shadow-glow transition-all duration-200 text-on-surface-variant hover:text-brand"
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