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
        :active="isActive(item)"
        @click="navigateTo(item.routeName)"
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
import { useRouter, useRoute } from 'vue-router'
import { useUIStore } from '@/stores/ui'
import NavRailItem from './NavRailItem.vue'
import { ChatDotRound, User, MagicStick, QuestionFilled, Setting, Search } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

const router = useRouter()
const route = useRoute()
const uiStore = useUIStore()

const navItems = [
  { id: 'chat', icon: ChatDotRound, label: 'Chat', routeName: 'chat' as const },
  { id: 'agents', icon: User, label: 'Agents', routeName: 'agents' as const },
  { id: 'skills', icon: MagicStick, label: 'Skills', routeName: 'skills' as const },
] as const

function isActive(item: { id: string; routeName: string }): boolean {
  if (item.id === 'chat') {
    return route.name === 'chat' || route.name === 'chat-detail'
  }
  if (item.id === 'agents') {
    return route.name === 'agents' || route.name === 'agent-create' || route.name === 'agent-edit'
  }
  if (item.id === 'skills') {
    return route.name === 'skills' || route.name === 'skill-create' || route.name === 'skill-edit'
  }
  return route.name === item.routeName
}

function navigateTo(routeName: string) {
  if (uiStore.sidebarCollapsed) {
    uiStore.sidebarCollapsed = false
  }
  router.push({ name: routeName })
}

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