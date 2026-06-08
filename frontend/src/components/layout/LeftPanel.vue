<template>
  <aside class="fixed left-0 top-0 h-full z-40 flex">
    <!-- Navigation Rail -->
    <div
      class="h-full overflow-hidden transition-all duration-300"
      style="transition-timing-function: cubic-bezier(0.16, 1, 0.3, 1);"
      :style="{ width: uiStore.navRailCollapsed ? '0px' : `${uiStore.navRailWidth}px` }"
    >
      <NavRail />
    </div>

    <!-- Resize handle between NavRail and ListPanel -->
    <div
      v-if="!uiStore.navRailCollapsed && !uiStore.sidebarCollapsed"
      class="relative h-full z-50 cursor-col-resize group flex items-center"
      style="width: 6px; margin-left: -3px; margin-right: -3px;"
      @mousedown="startResize"
    >
      <div class="h-full w-0.5 group-hover:w-1 bg-transparent group-hover:bg-brand/40 transition-all duration-150 mx-auto" />
    </div>

    <!-- Secondary List Panel -->
    <div
      class="h-full overflow-hidden transition-all duration-300"
      style="transition-timing-function: cubic-bezier(0.16, 1, 0.3, 1);"
      :style="{ width: (uiStore.navRailCollapsed || uiStore.sidebarCollapsed) ? '0px' : `${uiStore.listPanelWidth}px` }"
    >
      <ListPanel />
    </div>

    <!-- Collapse toggle button -->
    <button
      v-if="!uiStore.navRailCollapsed"
      class="absolute top-1/2 z-50 flex flex-col items-center justify-center gap-1 bg-white border border-outline-variant shadow-card hover:bg-brand hover:border-brand hover:text-white hover:shadow-glow transition-all duration-200 text-on-surface-variant rounded-lg w-4 h-16"
      :style="{ left: uiStore.sidebarCollapsed ? `${uiStore.navRailWidth}px` : `${uiStore.navRailWidth + uiStore.listPanelWidth}px`, transform: 'translate(-50%, -50%)' }"
      @click="uiStore.toggleSidebar"
    >
      <el-icon :size="12">
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

function startResize(e: MouseEvent) {
  e.preventDefault()
  const startX = e.clientX
  const startWidth = uiStore.navRailWidth

  function onMove(ev: MouseEvent) {
    uiStore.setNavRailWidth(startWidth + (ev.clientX - startX))
  }

  function onUp() {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }

  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}
</script>
