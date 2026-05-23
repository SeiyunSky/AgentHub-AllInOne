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