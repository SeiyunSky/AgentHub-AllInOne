import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ActiveArtifact, ArtifactItem } from '@/types/artifact'

export const useUIStore = defineStore('ui', () => {
  // Sidebar
  const sidebarCollapsed = ref(false)
  const navRailCollapsed = ref(false)

  function toggleNavRail() {
    navRailCollapsed.value = !navRailCollapsed.value
  }

  // Panel sizes (percentage for splitpanes)
  const chatPanePercent = ref(55)

  // Right panel
  const rightPanelActiveTab = ref<'workflow' | 'files' | 'preview'>('workflow')
  const rightPanelVisible = ref(false)
  // 进入 preview tab 之前的 tab(workflow / files),关闭预览后回到这里
  const lastNonPreviewTab = ref<'workflow' | 'files'>('workflow')

  // Artifact preview
  const activeArtifact = ref<ActiveArtifact | null>(null)

  // Legacy - no longer used for resizing, but kept for compatibility
  const isResizing = ref(false)

  const sidebarWidth = computed(() => {
    if (navRailCollapsed.value) return 0
    return sidebarCollapsed.value ? 160 : 440
  })

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function openArtifact(messageId: string, item: ArtifactItem, itemIndex: number) {
    activeArtifact.value = {
      id: messageId ? `${messageId}-${itemIndex}` : `sandbox-${item.convId ?? ''}-${item.path ?? item.name}`,
      messageId,
      item,
      mode: 'preview',
    }
    // 记下进 preview 之前的 tab,关闭后回到这里
    if (rightPanelActiveTab.value !== 'preview') {
      lastNonPreviewTab.value = rightPanelActiveTab.value
    }
    rightPanelActiveTab.value = 'preview'
    rightPanelVisible.value = true
  }

  function closeArtifact() {
    activeArtifact.value = null
    rightPanelActiveTab.value = lastNonPreviewTab.value
  }

  function setRightPanelTab(tab: 'workflow' | 'files' | 'preview') {
    if (tab !== 'preview') {
      lastNonPreviewTab.value = tab
    }
    rightPanelActiveTab.value = tab
    rightPanelVisible.value = true
  }

  function setPreviewMode(mode: 'preview' | 'edit') {
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
    navRailCollapsed,
    sidebarCollapsed,
    chatPanePercent,
    rightPanelActiveTab,
    rightPanelVisible,
    lastNonPreviewTab,
    activeArtifact,
    isResizing,
    sidebarWidth,
    toggleNavRail,
    toggleSidebar,
    openArtifact,
    closeArtifact,
    setPreviewMode,
    setRightPanelTab,
    toggleRightPanel,
    setChatPanePercent,
    startResizing,
    stopResizing,
    updatePanelWidths,
  }
})