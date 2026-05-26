<template>
  <div class="px-4 py-4">
    <div class="text-[10px] uppercase font-semibold text-on-surface-variant tracking-widest mb-3">Active Agents</div>
    <div class="space-y-2">
      <!-- New Agent -->
      <div
        class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-brand hover:bg-brand-light/30 cursor-pointer transition-colors"
        @click="router.push({ name: 'agent-create' })"
      >
        <el-icon :size="16"><Plus /></el-icon>
        <span class="text-[13px] font-medium">New Agent</span>
      </div>
      <!-- Agent list -->
      <div
        v-for="agent in agentsStore.agents"
        :key="agent.id"
        class="group p-3 rounded-xl bg-white border border-outline-variant hover:border-brand hover:bg-brand-light/40 cursor-pointer transition-all duration-200 hover-lift"
        :class="{ 'list-active !border-brand': agent.isActive }"
        @click="router.push({ name: 'agent-edit', params: { agentId: agent.id } })"
      >
        <div class="flex items-center gap-3">
          <div
            class="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 border transition-colors"
            :class="agent.isActive ? 'bg-gradient-to-br from-brand-light to-brand-subtle border-brand/20' : 'bg-surface-container border-transparent'"
          >
            <el-icon :class="agent.isActive ? 'text-brand' : 'text-on-surface-variant'" :size="16"><User /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[13px] font-semibold text-on-surface truncate">{{ agent.name }}</p>
            <p class="text-[11px] text-on-surface-variant truncate">{{ agent.type }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { User, Plus } from '@element-plus/icons-vue'
import { useAgentsStore } from '@/stores/agents'
import { agentsApi } from '@/api/agents'

const router = useRouter()
const agentsStore = useAgentsStore()

onMounted(async () => {
  if (agentsStore.agents.length === 0) {
    const data = await agentsApi.list()
    agentsStore.agents = data.map(a => ({
      id: a.id,
      name: a.name,
      description: a.description,
      type: a.type as any,
      avatar: a.avatar,
      systemPrompt: a.system_prompt,
      capabilities: {
        supportsCode: a.capabilities.supports_code,
        supportsDiff: a.capabilities.supports_diff,
        supportsApproval: a.capabilities.supports_approval,
        supportsImage: a.capabilities.supports_image,
      },
      tags: a.tags,
      isPublic: a.is_public,
      isActive: a.is_active,
      createdAt: new Date(a.created_at),
      updatedAt: new Date(a.updated_at),
    }))
  }
})
</script>
