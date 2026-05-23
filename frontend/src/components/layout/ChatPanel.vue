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

// Mock data demonstrating all block types
const messages = ref<Message[]>([
  {
    id: '1',
    type: 'agent',
    agentId: 'orchestrator',
    agentName: 'Orchestrator',
    agentRole: 'Host',
    agentRoleColor: 'brand',
    content: '',
    timestamp: new Date(Date.now() - 300000),
    blocks: [
      { type: 'text', content: "I'll analyze the sales data and coordinate with the team. Let me start by thinking through the approach." },
      {
        type: 'thinking',
        content: 'The user wants to process Q4 sales data. I should:\n1. First locate the data files\n2. Check the format and structure\n3. Dispatch to Data Analyst for processing\n4. Coordinate with Report Generator for output',
        duration: 2500,
      },
    ],
  },
  {
    id: '2',
    type: 'user',
    content: 'Can you help me process the Q4 sales data and generate a summary report?',
    timestamp: new Date(Date.now() - 240000),
  },
  {
    id: '3',
    type: 'agent',
    agentId: 'orchestrator',
    agentName: 'Orchestrator',
    agentRole: 'Host',
    agentRoleColor: 'brand',
    content: '',
    timestamp: new Date(Date.now() - 220000),
    blocks: [
      { type: 'text', content: 'Dispatching tasks to the relevant agents.' },
      {
        type: 'tool_use',
        toolName: 'dispatch_agent',
        input: { agent: 'data-analyst', task: 'load_csv', files: ['sales_q4.csv'] },
        output: 'Agent dispatched successfully',
        status: 'completed',
      },
    ],
  },
  {
    id: '4',
    type: 'agent',
    agentId: 'data-analyst',
    agentName: 'Data Analyst',
    agentRole: 'Processing',
    agentRoleColor: 'warning',
    content: '',
    timestamp: new Date(Date.now() - 180000),
    blocks: [
      {
        type: 'tool_use',
        toolName: 'read_file',
        input: { path: 'sales_q4.csv' },
        status: 'running',
      },
      { type: 'text', content: 'Found 3 CSV files in the target directory. Processing records...' },
      {
        type: 'code',
        code: `import pandas as pd

def load_data():
    df = pd.read_csv('sales_q4.csv')
    data = df.to_dict('records')
    print(f"Loaded {len(data)} records")
    return data`,
        filename: 'sales_q4.csv',
        language: 'python',
      },
    ],
  },
  {
    id: '5',
    type: 'agent',
    agentId: 'orchestrator',
    agentName: 'Orchestrator',
    agentRole: 'Host',
    agentRoleColor: 'brand',
    content: '',
    timestamp: new Date(Date.now() - 120000),
    blocks: [
      { type: 'text', content: 'The data has been loaded successfully. Now dispatching to the report generator agent.' },
      {
        type: 'tool_use',
        toolName: 'dispatch_agent',
        input: { agent: 'report-generator', task: 'create_summary', data: 'sales_q4' },
        output: 'Agent dispatched successfully',
        status: 'completed',
      },
    ],
  },
  {
    id: '6',
    type: 'user',
    content: 'Can you also include a comparison with Q3 data?',
    timestamp: new Date(Date.now() - 90000),
  },
  {
    id: '7',
    type: 'agent',
    agentId: 'data-analyst',
    agentName: 'Data Analyst',
    agentRole: 'Active',
    agentRoleColor: 'success',
    content: '',
    timestamp: new Date(Date.now() - 60000),
    blocks: [
      {
        type: 'thinking',
        content: 'User wants Q3 comparison. I need to:\n1. Load Q3 data\n2. Merge with Q4\n3. Calculate differences',
        duration: 1500,
      },
      { type: 'text', content: "I've merged the Q3 data for comparison. Here are the initial findings:" },
      {
        type: 'code',
        code: `import pandas as pd

def compare_quarters(q3, q4):
    q3_data = pd.read_csv(q3)
    q4_data = pd.read_csv(q4)
    merged = pd.merge(q3_data, q4_data, on='product_id')
    merged['growth'] = (merged['q4_sales'] - merged['q3_sales']) / merged['q3_sales']
    return merged`,
        filename: 'quarter_comparison.py',
        language: 'python',
        oldCode: `import pandas as pd

def load_data():
    df = pd.read_csv('sales_q4.csv')
    return df`,
      },
    ],
  },
  {
    id: '8',
    type: 'agent',
    agentId: 'report-generator',
    agentName: 'Report Generator',
    agentRole: 'Creating',
    agentRoleColor: 'warning',
    content: '',
    timestamp: new Date(Date.now() - 45000),
    blocks: [
      { type: 'text', content: 'Generating the summary report with charts and visualizations...' },
      {
        type: 'code',
        code: `import matplotlib.pyplot as plt
import pandas as pd

def create_comparison_chart(q3_data, q4_data):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(['Q3', 'Q4'], [q3_data['revenue'], q4_data['revenue']])
    ax.set_title('Quarter Revenue Comparison')
    plt.savefig('comparison_chart.png')
    return fig`,
        filename: 'generate_report.py',
        language: 'python',
      },
      {
        type: 'image',
        src: 'https://via.placeholder.com/400x250/3b82f6/ffffff?text=Revenue+Chart',
        caption: 'Quarter Revenue Comparison Chart',
      },
    ],
  },
  {
    id: '9',
    type: 'agent',
    agentId: 'orchestrator',
    agentName: 'Orchestrator',
    agentRole: 'Host',
    agentRoleColor: 'brand',
    content: '',
    timestamp: new Date(Date.now() - 30000),
    blocks: [
      { type: 'text', content: "Excellent work! The report is ready. Let me deploy it to the preview environment." },
      {
        type: 'deployment',
        title: 'Report Preview',
        status: 'completed',
        url: 'https://preview.example.com/reports/q4-sales',
        logs: 'Build completed in 2.3s\nDeployed to https://preview.example.com/reports/q4-sales',
        progress: 100,
      },
      {
        type: 'artifacts',
        title: 'Generated Artifacts',
        items: [
          { name: 'q4_sales_report.pdf', type: 'PDF' },
          { name: 'comparison_chart.png', type: 'Image' },
          { name: 'quarter_comparison.py', type: 'Code' },
        ],
      },
    ],
  },
  {
    id: '10',
    type: 'user',
    content: 'Great! Can you also add a breakdown by region?',
    timestamp: new Date(Date.now() - 15000),
  },
  {
    id: '11',
    type: 'agent',
    agentId: 'data-analyst',
    agentName: 'Data Analyst',
    agentRole: 'Processing',
    agentRoleColor: 'warning',
    content: '',
    timestamp: new Date(Date.now() - 10000),
    blocks: [
      {
        type: 'tool_use',
        toolName: 'query_database',
        input: { table: 'sales', groupBy: 'region' },
        status: 'running',
      },
      { type: 'text', content: 'Analyzing regional distribution from the dataset...' },
    ],
  },
  {
    id: '12',
    type: 'typing',
    agentId: 'report-generator',
    agentName: 'Report Generator',
    timestamp: new Date(),
  },
])

function onSend(content: string) {
  messages.value.push({
    id: String(Date.now()),
    type: 'user',
    content,
    timestamp: new Date(),
  })
}
</script>