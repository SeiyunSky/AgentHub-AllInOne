<template>
  <ChatContainer
    :title="'Active Thread'"
    :status="'3 agents listening'"
    :messages="messages"
    @send="onSend"
  >
    <template #headerActions>
      <el-button circle text size="small" class="!text-on-surface-variant hover:!bg-surface-container">
        <el-icon :size="16"><MoreFilled /></el-icon>
      </el-button>
      <el-button circle text size="small" class="!text-on-surface-variant hover:!bg-surface-container" @click="uiStore.rightPanelVisible = !uiStore.rightPanelVisible">
        <el-icon :size="16">
          <ArrowRight v-if="uiStore.rightPanelVisible" />
          <ArrowLeft v-else />
        </el-icon>
      </el-button>
    </template>
  </ChatContainer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useUIStore } from '@/stores/ui'
import ChatContainer from '@/components/chat/ChatContainer.vue'
import type { Message } from '@/types/chat'
import { MoreFilled, ArrowRight, ArrowLeft } from '@element-plus/icons-vue'

const uiStore = useUIStore()

// Mock data — will be replaced with store data
const messages = ref<Message[]>([
  {
    id: '1',
    type: 'agent',
    agentId: 'orchestrator',
    agentName: 'Orchestrator',
    agentRole: 'Host',
    agentRoleColor: 'brand',
    content: "I'll analyze the sales data and coordinate with the team. Let me dispatch tasks to the relevant agents.",
    timestamp: new Date(Date.now() - 120000),
  },
  {
    id: '2',
    type: 'user',
    content: 'Can you help me process the Q4 sales data and generate a summary report?',
    timestamp: new Date(Date.now() - 60000),
  },
  {
    id: '3',
    type: 'agent',
    agentId: 'data-analyst',
    agentName: 'Data Analyst',
    agentRole: 'Processing',
    agentRoleColor: 'warning',
    content: 'Found 3 CSV files in the target directory. Processing records...',
    timestamp: new Date(),
    codeBlock: {
      filename: 'sales_q4.csv',
      language: 'python',
      code: "import pandas as pd\ndf = pd.read_csv('sales_q4.csv')",
      diff: { added: 142, removed: 3 },
    },
  },
  {
    id: '4',
    type: 'typing',
    agentId: 'orchestrator',
    agentName: 'Orchestrator',
    timestamp: new Date(),
  },
])

function onSend(content: string) {
  // TODO: integrate with chat store
  messages.value.push({
    id: String(Date.now()),
    type: 'user',
    content,
    timestamp: new Date(),
  })
}
</script>