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
      <!-- Content: Chat + Right Panel via Splitpanes -->
      <main class="flex-1 overflow-hidden">
        <Splitpanes class="splitpanes-theme" @resized="onPaneResized">
          <Pane :size="chatPaneSize" :min-size="chatPaneMinSize" :max-size="chatPaneMaxSize">
            <ChatPanel />
          </Pane>
          <Pane v-if="uiStore.rightPanelVisible" :min-size="rightPaneMinSize">
            <RightPanel />
          </Pane>
        </Splitpanes>
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

const uiStore = useUIStore()

// Splitpanes uses percentage sizes. Calculate from pixel defaults.
// Chat panel ~420px out of ~1200px total ≈ 35%
const chatPaneSize = computed(() => uiStore.chatPanePercent)
const chatPaneMinSize = 35  // ~300px
const rightPaneMinSize = 25 // ~360px

function onPaneResized(event: ({ min: number; max: number; size: number })[]) {
  if (event.length > 0) {
    uiStore.chatPanePercent = event[0].size
  }
}
</script>