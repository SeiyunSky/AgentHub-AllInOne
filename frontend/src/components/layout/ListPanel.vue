<template>
  <div class="w-[240px] bg-white border-r border-outline-variant flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="px-4 h-16 flex flex-col justify-center border-b border-outline-variant bg-gradient-to-b from-white to-surface">
      <h1 class="text-base font-semibold text-on-surface tracking-tight">Nexus AI</h1>
      <p class="text-[10px] uppercase font-semibold text-on-surface-variant tracking-widest">Agent Orchestrator</p>
    </div>

    <!-- Content based on active tab -->
    <div class="flex-1 overflow-y-auto custom-scrollbar bg-surface">
      <ConversationList v-if="uiStore.sidebarActiveTab === 'chat'" />
      <AgentContactList v-else-if="uiStore.sidebarActiveTab === 'agents'" />
      <SkillsList v-else-if="uiStore.sidebarActiveTab === 'skills'" />
      <ProjectsList v-else-if="uiStore.sidebarActiveTab === 'projects'" />
    </div>

    <!-- Footer: Workspace -->
    <div class="px-3 py-3 border-t border-outline-variant bg-white">
      <div class="px-3 py-2 bg-gradient-to-r from-brand-light to-brand-subtle rounded-lg flex items-center gap-3 border border-brand/20 shadow-soft">
        <div class="w-2.5 h-2.5 rounded-full bg-brand shrink-0 shadow-glow"></div>
        <div class="overflow-hidden min-w-0">
          <p class="text-[11px] font-semibold text-on-surface truncate">Admin Workspace</p>
          <p class="text-[9px] text-brand-dark uppercase tracking-wide font-semibold">Premium</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useUIStore } from '@/stores/ui'
import ConversationList from '@/components/sidebar/ConversationList.vue'
import AgentContactList from '@/components/sidebar/AgentContactList.vue'
import SkillsList from './SkillsList.vue'
import ProjectsList from './ProjectsList.vue'

const uiStore = useUIStore()
</script>