import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUIStore = defineStore('ui', () => {
  // Sidebar
  const sidebarCollapsed = ref(false)
  const sidebarActiveTab = ref<'chat' | 'agents' | 'skills' | 'projects'>('chat')

  // Panel sizes (percentage for splitpanes)
  const chatPanePercent = ref(35)

  // Right panel
  const rightPanelActiveTab = ref<'workflow' | 'preview'>('workflow')
  const rightPanelVisible = ref(true)

  // Legacy - no longer used for resizing, but kept for compatibility
  const isResizing = ref(false)

  const sidebarWidth = computed(() => sidebarCollapsed.value ? 160 : 400)

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function setSidebarTab(tab: typeof sidebarActiveTab.value) {
    sidebarActiveTab.value = tab
    if (sidebarCollapsed.value) {
      sidebarCollapsed.value = false
    }
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
    sidebarActiveTab,
    chatPanePercent,
    rightPanelActiveTab,
    rightPanelVisible,
    isResizing,
    sidebarWidth,
    toggleSidebar,
    setSidebarTab,
    startResizing,
    stopResizing,
    updatePanelWidths,
  }
})