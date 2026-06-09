<template>
  <div
    v-if="streamingAgents.length > 0"
    class="px-4 py-2 border-t border-outline-variant bg-surface flex items-center gap-2"
  >
    <!-- 叠放头像 -->
    <div class="flex items-center">
      <div
        v-for="(agent, i) in streamingAgents"
        :key="agent.agentId"
        class="w-5 h-5 rounded-full shrink-0 overflow-hidden bg-brand-light flex items-center justify-center ring-2 ring-surface"
        :class="i > 0 ? '-ml-2' : ''"
        :title="agent.agentName"
      >
        <img v-if="resolveAvatar(agent)" :src="resolveAvatar(agent)" :alt="agent.agentName" class="w-full h-full object-cover" />
        <span v-else class="text-[9px] font-bold text-brand">{{ agent.agentName.charAt(0).toUpperCase() }}</span>
      </div>
    </div>

    <!-- 单一状态文字 -->
    <span class="text-[12px] text-on-surface-variant">
      {{ streamingAgents.length === 1 ? streamingAgents[0].agentName : `${streamingAgents.length} 个 Agent` }}
      <span class="text-on-surface-variant/60">正在思考</span>
    </span>

    <!-- 跳动点 -->
    <span class="flex items-center gap-0.5">
      <span class="w-1 h-1 rounded-full bg-on-surface-variant/50 animate-bounce [animation-delay:0ms]"></span>
      <span class="w-1 h-1 rounded-full bg-on-surface-variant/50 animate-bounce [animation-delay:150ms]"></span>
      <span class="w-1 h-1 rounded-full bg-on-surface-variant/50 animate-bounce [animation-delay:300ms]"></span>
    </span>
  </div>
</template>

<script setup lang="ts">
import { useAgentsStore } from '@/stores/agents'
import type { AgentStreamingState } from '@/stores/chat'

defineProps<{
  streamingAgents: AgentStreamingState[]
}>()

const agentsStore = useAgentsStore()

function resolveAvatar(agent: AgentStreamingState): string | undefined {
  return agent.avatar ?? agentsStore.agents.find(a => a.id === agent.agentId)?.avatar
}
</script>
