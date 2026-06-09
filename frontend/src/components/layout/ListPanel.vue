<template>
  <div class="w-[280px] h-full bg-white border-r border-outline-variant flex flex-col overflow-hidden">
    <!-- Content based on active tab derived from route -->
    <div class="flex-1 overflow-y-auto custom-scrollbar bg-surface">
      <ConversationList v-if="activeTab === 'chat'" />
      <AgentContactList v-else-if="activeTab === 'agents'" />
      <SkillsList v-else-if="activeTab === 'skills'" />
      <MCPServersList v-else-if="activeTab === 'mcp-servers'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useSidebarTab } from '@/composables/useSidebarTab'
import ConversationList from '@/components/sidebar/ConversationList.vue'
import AgentContactList from '@/components/sidebar/AgentContactList.vue'
import SkillsList from '@/components/sidebar/SkillsList.vue'
import MCPServersList from '@/components/sidebar/MCPServersList.vue'

const activeTab = useSidebarTab()
</script>
