<template>
  <div class="px-4 py-4">
    <div class="text-[10px] uppercase font-semibold text-on-surface-variant tracking-widest mb-3">Active Agents</div>
    <div class="space-y-2">
      <div
        v-for="agent in mockAgents"
        :key="agent.id"
        class="group p-3 rounded-xl bg-white border border-outline-variant hover:border-brand hover:bg-brand-light/40 cursor-pointer transition-all duration-200 hover-lift"
        :class="{ 'list-active !border-brand': agent.active }"
      >
        <div class="flex items-center gap-3">
          <div
            class="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 border transition-colors"
            :class="agent.active ? 'bg-gradient-to-br from-brand-light to-brand-subtle border-brand/20' : 'bg-surface-container border-transparent'"
          >
            <el-icon :class="agent.active ? 'text-brand' : 'text-on-surface-variant'" :size="16"><User /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[13px] font-semibold text-on-surface truncate">{{ agent.name }}</p>
            <p
              class="text-[11px] truncate"
              :class="agent.status === 'Processing...' ? 'text-warning font-medium' : 'text-on-surface-variant'"
            >
              {{ agent.status }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { User } from '@element-plus/icons-vue'

const mockAgents = [
  { id: '1', name: 'Orchestrator', status: 'Primary Host', active: true },
  { id: '2', name: 'Data Analyst', status: 'Processing...' },
  { id: '3', name: 'Lead Developer', status: 'Idle' },
  { id: '4', name: 'QA Engineer', status: 'Available' },
]
</script>