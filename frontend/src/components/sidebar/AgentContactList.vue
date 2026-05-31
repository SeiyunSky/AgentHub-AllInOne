<template>
  <div class="px-4 py-4">
    <div class="text-[10px] uppercase font-semibold text-on-surface-variant tracking-widest mb-3">Active Agents</div>
    <div class="space-y-2">
      <!-- New Agent -->
      <div
        class="flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-colors"
        :class="isSelected('new') ? 'bg-brand-light/50 text-brand' : 'text-brand hover:bg-brand-light/30'"
        @click="router.push({ name: 'agent-create' })"
      >
        <el-icon :size="16"><Plus /></el-icon>
        <span class="text-[13px] font-medium">New Agent</span>
      </div>
      <!-- Agent list -->
      <div
        v-for="agent in agentsStore.agents"
        :key="agent.id"
        class="group p-3 rounded-xl bg-white border cursor-pointer transition-all duration-200 hover-lift"
        :class="isSelected(agent.id) ? 'border-brand bg-brand-light/40' : 'border-outline-variant hover:border-brand hover:bg-brand-light/40'"
        @click="router.push({ name: 'agent-edit', params: { agentId: agent.id } })"
      >
        <div class="flex items-center gap-3">
          <div
            class="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 border bg-surface-container border-transparent transition-colors"
          >
            <el-icon class="text-on-surface-variant" :size="16"><User /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[13px] font-semibold text-on-surface truncate">{{ agent.name }}</p>
            <p class="text-[11px] text-on-surface-variant truncate">{{ agent.type }}</p>
          </div>
          <span
            class="w-2 h-2 rounded-full shrink-0"
            :class="agent.isActive ? 'bg-emerald-400' : 'bg-outline'"
            :title="agent.isActive ? 'Active' : 'Inactive'"
          ></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Plus } from '@element-plus/icons-vue'
import { useAgentsStore } from '@/stores/agents'

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

onMounted(() => {
  agentsStore.loadAgents()
})
</script>