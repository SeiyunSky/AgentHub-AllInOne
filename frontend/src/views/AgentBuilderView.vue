<template>
  <div class="fixed inset-0 flex bg-surface text-on-surface overflow-hidden">
    <!-- Left Sidebar -->
    <LeftPanel />

    <!-- Main Content Area -->
    <div
      id="main-content"
      class="flex-1 flex flex-col transition-all duration-300 overflow-hidden"
      :style="{ marginLeft: `${uiStore.sidebarWidth}px` }"
    >
      <main class="flex-1 overflow-hidden">
        <Splitpanes class="splitpanes-theme">
          <Pane :size="70" :min-size="50">
            <PanelContainer
              :title="isEditMode ? 'Edit Agent' : 'Create Agent'"
              :icon="Setting"
              variant="brand"
            >
              <AgentForm v-model="agentsStore.currentDraft" />
              <template #toolbar>
                <div class="flex items-center gap-2">
                  <button
                    v-if="!isEditMode"
                    class="h-8 px-4 rounded-lg flex items-center gap-2 bg-brand text-white text-[13px] font-medium shadow-sm hover:bg-brand-dark transition-colors cursor-pointer"
                    @click="saveAgent"
                  >
                    <el-icon :size="14"><Select /></el-icon>
                    Create
                  </button>
                  <button
                    class="h-8 px-3 rounded-lg flex items-center gap-1 text-on-surface-variant hover:bg-surface-container transition-colors cursor-pointer"
                    @click="showChat = !showChat"
                  >
                    <el-icon :size="14"><Fold /></el-icon>
                  </button>
                </div>
              </template>
            </PanelContainer>
          </Pane>
          <Pane v-if="showChat" :size="30" :min-size="20">
            <ChatContainer
              title="Builder Assistant"
              status="Online"
              :messages="assistantMessages"
              @send="onAssistantSend"
            />
          </Pane>
        </Splitpanes>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Splitpanes, Pane } from 'splitpanes'
import 'splitpanes/dist/splitpanes.css'
import { useUIStore } from '@/stores/ui'
import { useAgentsStore } from '@/stores/agents'
import { agentsApi } from '@/api/agents'
import PanelContainer from '@/components/layout/PanelContainer.vue'
import ChatContainer from '@/components/chat/ChatContainer.vue'
import AgentForm from '@/components/agents/AgentForm.vue'
import LeftPanel from '@/components/layout/LeftPanel.vue'
import type { Message } from '@/types/chat'
import { Setting, Select, Fold } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const uiStore = useUIStore()
const agentsStore = useAgentsStore()

const agentId = computed(() => route.params.agentId as string | undefined)
const isEditMode = computed(() => !!agentId.value && agentId.value !== 'new')

const assistantMessages = ref<Message[]>([
  {
    id: '1',
    type: 'agent',
    agentId: 'builder-assistant',
    agentName: 'Builder Assistant',
    agentRole: 'Helper',
    agentRoleColor: 'success',
    content: 'Hello! I can help you create or configure your agent. Ask me about system prompts, capabilities, or best practices for agent design.',
    timestamp: new Date(Date.now() - 60000),
  },
])

const showChat = ref(true)

onMounted(async () => {
  if (isEditMode.value && agentId.value) {
    const agent = await agentsApi.get(agentId.value)
    if (agent) {
      agentsStore.loadFromAgent(agent)
    }
  } else {
    agentsStore.resetDraft()
  }
})

async function saveAgent() {
  await agentsApi.create(agentsStore.currentDraft)
  router.push({ name: 'agents' })
}

function onAssistantSend(content: string, _mentions: string[], _replyToId?: string) {
  assistantMessages.value.push({
    id: String(Date.now()),
    type: 'user',
    content,
    timestamp: new Date(),
  })

  // Mock response
  setTimeout(() => {
    assistantMessages.value.push({
      id: String(Date.now() + 1),
      type: 'agent',
      agentId: 'builder-assistant',
      agentName: 'Builder Assistant',
      agentRole: 'Helper',
      agentRoleColor: 'success',
      content: getMockResponse(content),
      timestamp: new Date(),
    })
  }, 1000)
}

function getMockResponse(question: string): string {
  if (question.toLowerCase().includes('prompt')) {
    return 'A good system prompt should clearly define the agent\'s role, expertise, and response style. For example, a code review agent might use: "You are a senior developer who reviews code for quality, security, and performance..."'
  }
  if (question.toLowerCase().includes('capability')) {
    return 'Capabilities define what your agent can do. Enable "Code Execution" for agents that need to run code, "Diff Support" for code modification, "Approval Workflow" for agents that require user confirmation, and "Image Processing" for visual tasks.'
  }
  return 'I\'m here to help you build great agents! Feel free to ask about system prompts, capabilities, model settings, or general agent design principles.'
}
</script>