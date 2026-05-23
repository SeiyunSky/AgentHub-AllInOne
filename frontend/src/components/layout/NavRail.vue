<template>
  <nav class="w-[68px] bg-rail-bg h-full flex flex-col items-center py-5 gap-2 shrink-0 border-r border-rail-border">
    <!-- Logo -->
    <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-brand to-brand-dark flex items-center justify-center text-white font-bold text-lg shadow-glow mb-2">
      N
    </div>

    <!-- Primary Nav Icons -->
    <div class="flex-1 flex flex-col items-center gap-1 w-full mt-2">
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
    <div class="flex flex-col items-center gap-1 w-full border-t border-rail-border pt-4">
      <NavRailItem :icon="QuestionFilled" label="Support" />
      <NavRailItem :icon="Setting" label="Settings" />
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useUIStore } from '@/stores/ui'
import NavRailItem from './NavRailItem.vue'
import { ChatDotRound, User, MagicStick, FolderOpened, QuestionFilled, Setting } from '@element-plus/icons-vue'

const uiStore = useUIStore()

const navItems = [
  { id: 'chat', icon: ChatDotRound, label: 'Chat' },
  { id: 'agents', icon: User, label: 'Agents' },
  { id: 'skills', icon: MagicStick, label: 'Skills' },
  { id: 'projects', icon: FolderOpened, label: 'Projects' },
] as const
</script>
