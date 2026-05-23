<template>
  <nav class="w-[160px] bg-rail-bg h-full flex flex-col py-4 shrink-0 border-r border-rail-border">
    <!-- Logo -->
    <div class="flex items-center gap-2.5 px-4 mb-4">
      <div class="w-9 h-9 rounded-lg bg-white/15 flex items-center justify-center text-white font-bold text-base shrink-0">N</div>
      <span class="text-white font-semibold text-sm">Nexus AI</span>
    </div>

    <!-- Search Button -->
    <button
      class="mx-3 flex items-center gap-2.5 py-2 px-3 rounded-lg text-white/50 hover:text-white/80 hover:bg-white/5 cursor-pointer transition-all duration-200"
      @click="showSearchDialog"
    >
      <el-icon :size="18"><Search /></el-icon>
      <span class="text-[13px] font-medium">Search</span>
    </button>

    <!-- Divider -->
    <div class="mx-4 h-px bg-white/10 my-3"></div>

    <!-- Primary Nav Icons -->
    <div class="flex-1 flex flex-col gap-1 w-full px-2">
      <NavRailItem
        v-for="item in navItems"
        :key="item.id"
        :icon="item.icon"
        :label="item.label"
        :active="uiStore.sidebarActiveTab === item.id"
        @click="uiStore.setSidebarTab(item.id)"
      />
    </div>

    <!-- Bottom Icons -->
    <div class="flex flex-col gap-1 w-full px-2 border-t border-rail-border pt-3 mt-3">
      <NavRailItem :icon="QuestionFilled" label="Support" />
      <NavRailItem :icon="Setting" label="Settings" />
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useUIStore } from '@/stores/ui'
import NavRailItem from './NavRailItem.vue'
import { ChatDotRound, User, MagicStick, FolderOpened, QuestionFilled, Setting, Search } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

const uiStore = useUIStore()

const navItems = [
  { id: 'chat', icon: ChatDotRound, label: 'Chat' },
  { id: 'agents', icon: User, label: 'Agents' },
  { id: 'skills', icon: MagicStick, label: 'Skills' },
  { id: 'projects', icon: FolderOpened, label: 'Projects' },
] as const

function showSearchDialog() {
  // TODO: Replace with actual search modal
  ElMessageBox.prompt('', 'Search', {
    confirmButtonText: 'Search',
    cancelButtonText: 'Cancel',
    inputPlaceholder: 'Search conversations, agents, skills...',
    customStyle: {
      borderRadius: '16px',
    },
  }).catch(() => {})
}
</script>