import { computed } from 'vue'
import { useRoute } from 'vue-router'

export type SidebarTab = 'chat' | 'agents' | 'skills'

/**
 * Derives the active sidebar tab from the current route name.
 * Used by ListPanel and NavRail to determine which content to show/highlight.
 */
export function useSidebarTab() {
  const route = useRoute()

  const activeTab = computed<SidebarTab>(() => {
    const name = route.name as string
    if (name === 'chat' || name === 'chat-detail') return 'chat'
    if (name === 'agents' || name === 'agent-create' || name === 'agent-edit') return 'agents'
    if (name === 'skills' || name === 'skill-create' || name === 'skill-edit') return 'skills'
    return 'chat'
  })

  return activeTab
}
