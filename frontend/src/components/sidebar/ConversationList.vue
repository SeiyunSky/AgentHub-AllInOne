<template>
  <div class="px-4 py-4">
    <div class="text-[10px] uppercase font-semibold text-on-surface-variant tracking-widest mb-3">Recent Conversations</div>
    <div class="space-y-2">
      <!-- New Chat -->
      <div
        class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-brand hover:bg-brand-light/30 cursor-pointer transition-colors"
      >
        <el-icon :size="16"><Plus /></el-icon>
        <span class="text-[13px] font-medium">New Chat</span>
      </div>
      <!-- Conversation list -->
      <div
        v-for="conv in mockConversations"
        :key="conv.id"
        class="group p-3 rounded-xl bg-white border border-outline-variant hover:border-brand hover:bg-brand-light/40 cursor-pointer transition-all duration-200 hover-lift"
        :class="{ 'list-active !border-brand': conv.active }"
      >
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-lg bg-gradient-to-br from-brand-light to-brand-subtle flex items-center justify-center shrink-0 border border-brand/20">
            <el-icon class="text-brand" :size="16"><ChatDotRound /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[13px] font-semibold text-on-surface truncate">{{ conv.title }}</p>
            <p class="text-[11px] text-on-surface-variant truncate">{{ conv.preview }}</p>
          </div>
          <span v-if="conv.unread" class="bg-brand text-white text-[10px] font-semibold px-1.5 py-0.5 rounded-full shadow-soft">{{ conv.unread }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ChatDotRound, Plus } from '@element-plus/icons-vue'

const mockConversations = [
  { id: '1', title: 'Sales Automation Flow', preview: 'Orchestrator: Task completed...', active: true },
  { id: '2', title: 'Code Review Session', preview: 'Data Analyst: Here are my findings...', unread: 3 },
  { id: '3', title: 'API Integration Help', preview: 'Lead Developer: I can help with...' },
]
</script>