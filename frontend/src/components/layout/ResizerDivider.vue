<template>
  <div
    class="w-[3px] hover:w-[5px] bg-transparent hover:bg-brand/30 transition-all duration-200 cursor-col-resize flex items-center justify-center relative group z-20 shrink-0 h-full select-none"
    :class="{ '!w-[5px] bg-brand/40': uiStore.isResizing }"
    @mousedown="startResize"
  >
    <div class="w-3.5 h-6 bg-white border border-outline-variant rounded-md flex items-center justify-center shadow-card opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none"
      :class="{ '!opacity-100 !border-brand': uiStore.isResizing }"
    >
      <el-icon :size="10" class="text-on-surface-variant"><Rank /></el-icon>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onUnmounted } from 'vue'
import { useUIStore } from '@/stores/ui'
import { Rank } from '@element-plus/icons-vue'

const uiStore = useUIStore()

let startX = 0

function startResize(e: MouseEvent) {
  e.preventDefault()
  startX = e.clientX
  uiStore.startResizing()

  // Use passive listeners for better performance
  document.addEventListener('mousemove', onResize, { passive: true })
  document.addEventListener('mouseup', stopResize)
}

function onResize(e: MouseEvent) {
  if (!uiStore.isResizing) return
  const deltaX = e.clientX - startX
  startX = e.clientX
  uiStore.updatePanelWidths(deltaX)
}

function stopResize() {
  uiStore.stopResizing()
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
}

onUnmounted(() => {
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
})
</script>