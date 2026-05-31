<template>
  <div class="px-4 py-4">
    <div class="text-[10px] uppercase font-semibold text-on-surface-variant tracking-widest mb-3">Active Agents</div>
    <div class="space-y-2">
      <!-- New Agent -->
      <div
        class="flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200 border-2 border-dashed"
        :class="isSelected('new')
          ? 'border-brand bg-brand-light/40 text-brand'
          : 'border-outline-variant text-brand hover:border-brand/40 hover:bg-brand-light/20'"
        @click="router.push({ name: 'agent-create' })"
      >
        <div class="w-8 h-8 rounded-lg flex items-center justify-center bg-brand-light">
          <el-icon :size="16" class="text-brand"><Plus /></el-icon>
        </div>
        <span class="text-[13px] font-medium">New Agent</span>
      </div>
      <!-- Agent list -->
      <div
        v-for="agent in agentsStore.agents"
        :key="agent.id"
        class="group p-3 rounded-xl bg-white border cursor-pointer transition-all duration-200 hover-lift"
        :class="isSelected(agent.id)
          ? 'border-brand bg-brand-light/30'
          : 'border-outline-variant hover:border-brand/40'"
        @click="router.push({ name: 'agent-edit', params: { agentId: agent.id } })"
      >
        <div class="flex items-center gap-3">
          <div
            class="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 border overflow-hidden"
            :class="agentAvatarClass(agent.type)"
          >
            <img v-if="agent.avatar" :src="agent.avatar" :alt="agent.name" class="w-full h-full object-cover" />
            <img v-else :src="getAgentTypeIcon(agent.type)" :alt="agent.type" class="w-6 h-6 object-contain" @error="hideImg" />
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[13px] font-semibold text-on-surface truncate">{{ agent.name }}</p>
            <p class="text-[10px] text-on-surface-variant truncate capitalize">{{ agent.type }}</p>
          </div>
          <div
            class="shrink-0"
            :class="agent.isActive ? 'status-dot-active' : 'status-dot-inactive'"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Plus } from '@element-plus/icons-vue'
import { useAgentsStore } from '@/stores/agents'
import { getAgentTypeIcon } from '@/utils/agentIcons'

const router = useRouter()
const route = useRoute()
const agentsStore = useAgentsStore()

const currentAgentId = computed(() => route.params.agentId as string | undefined)

function isSelected(agentId: string) {
  if (agentId === 'new') {
    return route.name === 'agent-create'
  }
  return route.name === 'agent-edit' && currentAgentId.value === agentId
}

function agentAvatarClass(type: string) {
  const map: Record<string, string> = {
    claude: '',
    codex: '',
    opencode: '',
  }
  return map[type] || 'bg-surface-container border-outline-variant'
}

function hideImg(e: Event) {
  ;(e.target as HTMLImageElement).style.display = 'none'
}

onMounted(() => {
  agentsStore.loadAgents()
})
</script>
