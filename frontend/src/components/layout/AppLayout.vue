<template>
  <div class="fixed inset-0 flex bg-surface text-on-surface overflow-hidden">
    <!-- Left Sidebar -->
    <LeftPanel />

    <!-- Main Content Area -->
    <div
      id="main-content"
      class="flex-1 flex flex-col transition-all duration-300 overflow-hidden"
      :style="{ marginLeft: `${uiStore.sidebarWidth}px` }"
    >
      <!-- Content switches based on active sidebar tab -->
      <main class="flex-1 overflow-hidden">
        <!-- Chat view: Splitpanes with Chat + Right panel -->
        <Splitpanes v-if="uiStore.sidebarActiveTab === 'chat'" class="splitpanes-theme" @resized="onPaneResized">
          <Pane :size="chatPaneSize" :min-size="chatPaneMinSize" :max-size="chatPaneMaxSize">
            <ChatPanel />
          </Pane>
          <Pane v-if="uiStore.rightPanelVisible" :min-size="rightPaneMinSize">
            <RightPanel />
          </Pane>
        </Splitpanes>

        <!-- Agents view -->
        <AgentsPanel v-else-if="uiStore.sidebarActiveTab === 'agents'" />

        <!-- Skills view -->
        <SkillsPanel v-else-if="uiStore.sidebarActiveTab === 'skills'" />

        <!-- Projects view -->
        <ProjectsPanel v-else-if="uiStore.sidebarActiveTab === 'projects'" />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useUIStore } from '@/stores/ui'
import { Splitpanes, Pane } from 'splitpanes'
import 'splitpanes/dist/splitpanes.css'
import LeftPanel from './LeftPanel.vue'
import ChatPanel from './ChatPanel.vue'
import RightPanel from './RightPanel.vue'
import AgentsPanel from './AgentsPanel.vue'
import SkillsPanel from './SkillsPanel.vue'
import ProjectsPanel from './ProjectsPanel.vue'

const uiStore = useUIStore()

// Splitpanes uses percentage sizes. Calculate from pixel defaults.
// Chat panel ~420px out of ~1200px total ≈ 35%
const chatPaneSize = computed(() => uiStore.chatPanePercent)
const chatPaneMinSize = 35  // ~300px
const rightPaneMinSize = 25 // ~360px

function onPaneResized(event: ({ min: number; max: number; size: number })[]) {
  if (event.length > 0) {
    uiStore.setChatPanePercent(event[0].size)
  }
}
</script>