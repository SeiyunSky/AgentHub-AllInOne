import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ActiveArtifact, ArtifactItem } from '@/types/artifact'

export const useUIStore = defineStore('ui', () => {
  // Sidebar
  const sidebarCollapsed = ref(false)

  // Panel sizes (percentage for splitpanes)
  const chatPanePercent = ref(55)

  // Right panel
  const rightPanelActiveTab = ref<'workflow' | 'preview'>('workflow')
  const rightPanelVisible = ref(true)

  // Artifact preview
  const activeArtifact = ref<ActiveArtifact | null>(null)

  // Legacy - no longer used for resizing, but kept for compatibility
  const isResizing = ref(false)

  const sidebarWidth = computed(() => sidebarCollapsed.value ? 160 : 440)

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function openArtifact(messageId: string, item: ArtifactItem, itemIndex: number) {
    activeArtifact.value = {
      id: `${messageId}-${itemIndex}`,
      messageId,
      item,
      mode: 'preview',
    }
    rightPanelActiveTab.value = 'preview'
    rightPanelVisible.value = true
  }

  function closeArtifact() {
    activeArtifact.value = null
    rightPanelActiveTab.value = 'workflow'
  }

  function setPreviewMode(mode: 'preview' | 'code') {
    if (activeArtifact.value) {
      activeArtifact.value.mode = mode
    }
  }

  function toggleRightPanel() {
    if (!rightPanelVisible.value) {
      chatPanePercent.value = 70
    }
    rightPanelVisible.value = !rightPanelVisible.value
  }

  function setChatPanePercent(size: number) {
    chatPanePercent.value = size
  }

  // Legacy functions - kept for compatibility
  function startResizing() {
    isResizing.value = true
  }

  function stopResizing() {
    isResizing.value = false
  }

  function updatePanelWidths(_deltaX: number) {
    // No-op - splitpanes handles resizing now
  }

  return {
    sidebarCollapsed,
    chatPanePercent,
    rightPanelActiveTab,
    rightPanelVisible,
    activeArtifact,
    isResizing,
    sidebarWidth,
    toggleSidebar,
    openArtifact,
    closeArtifact,
    setPreviewMode,
    toggleRightPanel,
    setChatPanePercent,
    startResizing,
    stopResizing,
    updatePanelWidths,
  }
})