<template>
  <div class="fixed inset-0 flex bg-surface text-on-surface overflow-hidden">
    <!-- Left Sidebar -->
    <LeftPanel />

    <!-- Main Content Area — driven by router -->
    <div
      id="main-content"
      class="flex-1 flex flex-col transition-all duration-300 overflow-hidden"
      :style="{ marginLeft: `${uiStore.sidebarWidth}px` }"
    >
      <main class="flex-1 overflow-hidden">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useUIStore } from '@/stores/ui'
import LeftPanel from './LeftPanel.vue'

const uiStore = useUIStore()
</script>
