<template>
  <div class="w-[280px] h-full bg-white border-r border-outline-variant flex flex-col overflow-hidden">
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