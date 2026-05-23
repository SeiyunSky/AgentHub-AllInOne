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
      <!-- Top Header Bar -->
      <header class="h-14 glass-panel border-b border-outline-variant flex items-center px-6 shrink-0 z-10">
        <!-- Search -->
        <div class="flex items-center bg-surface border border-outline-variant rounded-full px-4 py-1.5 w-80 shadow-soft focus-within:border-brand focus-within:shadow-glow transition-all duration-200">
          <el-icon class="text-on-surface-variant mr-2.5 transition-colors" :size="16"><Search /></el-icon>
          <input
            class="bg-transparent border-none text-[13px] w-full placeholder-on-surface-variant/60 outline-none text-on-surface"
            placeholder="Search project assets..."
          />
          <kbd class="hidden sm:inline-flex items-center gap-0.5 text-[10px] text-on-surface-variant bg-white border border-outline-variant rounded px-1.5 py-0.5 ml-2 font-mono">/</kbd>
        </div>

        <div class="flex-1" />

        <!-- Right Actions -->
        <div class="flex items-center gap-2">
          <button class="w-9 h-9 rounded-xl flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors relative">
            <el-icon :size="18"><Monitor /></el-icon>
          </button>
          <button class="w-9 h-9 rounded-xl flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors relative">
            <el-icon :size="18"><Bell /></el-icon>
            <span class="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-full ring-2 ring-white"></span>
          </button>
          <div class="w-px h-5 bg-outline-variant mx-1"></div>
          <button class="w-9 h-9 rounded-xl bg-gradient-to-br from-brand to-brand-dark flex items-center justify-center text-white text-xs font-bold shadow-soft hover:shadow-glow hover:scale-105 active:scale-95 transition-all duration-200">
            A
          </button>
        </div>
      </header>

      <!-- Content: Chat + Right Panel via Splitpanes -->
      <main class="flex-1 overflow-hidden">
        <Splitpanes class="splitpanes-theme default-theme" @resized="onPaneResized">
          <Pane :size="chatPaneSize" :min-size="chatPaneMinSize">
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
import { Search, Monitor, Bell } from '@element-plus/icons-vue'

const uiStore = useUIStore()

// Splitpanes uses percentage sizes. Calculate from pixel defaults.
// Chat panel ~420px out of ~1200px total ≈ 35%
const chatPaneSize = computed(() => uiStore.chatPanePercent)
const chatPaneMinSize = 25  // ~300px
const rightPaneMinSize = 30 // ~360px

function onPaneResized(event: ({ min: number; max: number; size: number })[]) {
  if (event.length > 0) {
    uiStore.chatPanePercent = event[0].size
  }
}
</script>