<template>
  <el-dialog
    :model-value="modelValue"
    title="Build with AI"
    width="680px"
    :before-close="handleClose"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="flex flex-col gap-4" style="min-height: 400px;">
      <!-- Chat messages -->
      <div ref="messagesEl" class="flex-1 overflow-y-auto space-y-3 max-h-[320px] pr-1 custom-scrollbar">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="flex gap-2"
          :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <div
            class="max-w-[85%] px-3.5 py-2.5 rounded-2xl text-[13px] leading-relaxed"
            :class="msg.role === 'user'
              ? 'bg-brand text-white rounded-br-md'
              : 'bg-surface-container text-on-surface rounded-bl-md'"
          >
            {{ msg.content }}
          </div>
        </div>
        <!-- Typing indicator -->
        <div v-if="isThinking" class="flex gap-2 justify-start">
          <div class="bg-surface-container px-4 py-3 rounded-2xl rounded-bl-md">
            <div class="flex gap-1 items-center">
              <span class="w-1.5 h-1.5 bg-on-surface-variant rounded-full animate-bounce" style="animation-delay: 0ms"></span>
              <span class="w-1.5 h-1.5 bg-on-surface-variant rounded-full animate-bounce" style="animation-delay: 150ms"></span>
              <span class="w-1.5 h-1.5 bg-on-surface-variant rounded-full animate-bounce" style="animation-delay: 300ms"></span>
            </div>
          </div>
        </div>
      </div>

      <!-- Draft preview (shown once AI returns a draft) -->
      <div v-if="draft" class="rounded-xl border border-outline-variant bg-surface-container p-4 space-y-2">
        <p class="text-[11px] uppercase font-semibold text-on-surface-variant tracking-widest">Draft</p>
        <p class="text-[14px] font-semibold text-on-surface">{{ draft.name }}</p>
        <p v-if="draft.description" class="text-[12px] text-on-surface-variant">{{ draft.description }}</p>
        <div class="flex gap-2 mt-1">
          <span class="px-2 py-0.5 rounded-full text-[11px] font-medium bg-brand-light text-brand">{{ draft.type }}</span>
        </div>
      </div>

      <!-- Input -->
      <div class="flex gap-2 mt-auto">
        <el-input
          v-model="input"
          placeholder="Describe the agent you want to build..."
          :disabled="isThinking"
          @keyup.enter="sendMessage"
        />
        <el-button
          type="primary"
          :loading="isThinking"
          :disabled="!input.trim()"
          @click="sendMessage"
        >
          Send
        </el-button>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-between items-center">
        <el-button @click="handleClose">Cancel</el-button>
        <el-button
          type="primary"
          :disabled="!draft"
          @click="confirmDraft"
        >
          Use This Agent
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { AgentDraft } from '@/types/agent'
import { agentsApi } from '@/api/agents'
import type { AgentBuildDraft } from '@/api/agents'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'confirmed': [draft: AgentDraft]
}>()

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}

const messages = ref<ChatMessage[]>([
  {
    id: '0',
    role: 'assistant',
    content: 'Hi! Describe the agent you want to build and I\'ll generate a configuration for you. For example: "A customer support agent that handles refund requests professionally."',
  },
])
const input = ref('')
const isThinking = ref(false)
const draft = ref<AgentBuildDraft | null>(null)
const sessionId = ref<string | null>(null)
const messagesEl = ref<HTMLElement | null>(null)

watch(() => props.modelValue, (open) => {
  if (open) {
    messages.value = [{
      id: '0',
      role: 'assistant',
      content: 'Hi! Describe the agent you want to build and I\'ll generate a configuration for you.',
    }]
    draft.value = null
    sessionId.value = null
    input.value = ''
  }
})

async function sendMessage() {
  const text = input.value.trim()
  if (!text || isThinking.value) return

  messages.value.push({ id: String(Date.now()), role: 'user', content: text })
  input.value = ''
  isThinking.value = true
  await scrollToBottom()

  try {
    const result = await agentsApi.build(text)
    sessionId.value = result.session_id
    draft.value = result.draft
    messages.value.push({
      id: String(Date.now() + 1),
      role: 'assistant',
      content: `I've drafted an agent called "${result.draft.name}". You can review it above and click "Use This Agent" to create it, or keep chatting to refine.`,
    })
  } catch {
    messages.value.push({
      id: String(Date.now() + 1),
      role: 'assistant',
      content: 'Sorry, I had trouble generating the agent. Please try again.',
    })
    ElMessage.error('Build request failed')
  } finally {
    isThinking.value = false
    await scrollToBottom()
  }
}

async function confirmDraft() {
  if (!draft.value) return
  const agentDraft: AgentDraft = {
    name: draft.value.name,
    description: draft.value.description,
    type: draft.value.type as any,
    avatar: draft.value.avatar,
    systemPrompt: draft.value.system_prompt,
    capabilities: {
      supportsCode: draft.value.capabilities?.supports_code ?? false,
      supportsDiff: draft.value.capabilities?.supports_diff ?? false,
      supportsApproval: draft.value.capabilities?.supports_approval ?? false,
      supportsImage: draft.value.capabilities?.supports_image ?? false,
    },
    tags: draft.value.tags ?? [],
    isPublic: false,
  }
  emit('confirmed', agentDraft)
  emit('update:modelValue', false)
}

function handleClose() {
  emit('update:modelValue', false)
}

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}
</script>
