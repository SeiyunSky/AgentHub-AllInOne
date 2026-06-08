<template>
  <el-dialog
    :model-value="modelValue"
    width="720px"
    :show-close="false"
    :close-on-click-modal="false"
    custom-class="agent-builder-dialog"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <!-- Custom Header -->
    <template #header>
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-xl bg-brand flex items-center justify-center shadow-soft">
          <el-icon :size="18" class="text-white"><MagicStick /></el-icon>
        </div>
        <div>
          <h3 class="text-[15px] font-semibold text-on-surface leading-tight">{{ t('agentBuilder.title') }}</h3>
          <p class="text-[11px] text-on-surface-variant">{{ t('agentBuilder.subtitle') }}</p>
        </div>
      </div>
    </template>

    <div class="flex flex-col gap-4" style="min-height: 400px;">
      <!-- Chat messages -->
      <div ref="messagesEl" class="flex-1 overflow-y-auto space-y-3 max-h-[320px] pr-1 custom-scrollbar">
        <div v-for="msg in messages" :key="msg.id">
          <!-- User bubble -->
          <div v-if="msg.role === 'user'" class="flex justify-end">
            <div class="max-w-[80%] px-4 py-3 rounded-2xl rounded-br-md text-[13px] leading-relaxed bg-brand text-white shadow-soft">
              {{ msg.content }}
            </div>
          </div>
          <!-- Assistant bubble -->
          <div v-else class="flex gap-2.5 items-start justify-start">
            <div class="w-7 h-7 rounded-lg bg-brand-light flex items-center justify-center shrink-0 border border-brand/10">
              <el-icon :size="14" class="text-brand"><MagicStick /></el-icon>
            </div>
            <div class="max-w-[80%] px-4 py-3 rounded-2xl rounded-bl-md text-[13px] leading-relaxed bg-surface-container text-on-surface">
              {{ msg.content }}
            </div>
          </div>
        </div>
        <!-- Typing indicator -->
        <div v-if="isThinking" class="flex gap-2.5 items-start justify-start">
          <div class="w-7 h-7 rounded-lg bg-brand-light flex items-center justify-center shrink-0 border border-brand/10">
            <el-icon :size="14" class="text-brand"><MagicStick /></el-icon>
          </div>
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
      <div v-if="draft" class="rounded-xl border border-brand/20 bg-brand-light p-4 space-y-3 shadow-soft fade-in-up">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 rounded-lg bg-brand/10 flex items-center justify-center">
            <el-icon :size="14" class="text-brand"><User /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[14px] font-semibold text-on-surface truncate">{{ draft.name }}</p>
          </div>
          <span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-brand-light text-brand border border-brand/10 capitalize">
            {{ draft.type }}
          </span>
        </div>
        <p v-if="draft.description" class="text-[12px] text-on-surface-variant leading-relaxed">{{ draft.description }}</p>
        <div v-if="draft.tags && draft.tags.length" class="flex gap-1.5 flex-wrap">
          <span v-for="tag in draft.tags" :key="tag" class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-surface-container text-on-surface-variant">
            {{ tag }}
          </span>
        </div>
      </div>

      <!-- Input -->
      <div class="flex items-center gap-2 mt-auto pt-3 border-t border-outline-variant">
        <div class="flex-1 relative">
          <input
            v-model="input"
            type="text"
            :placeholder="t('agentBuilder.inputPlaceholder')"
            class="w-full pl-4 pr-4 py-2.5 rounded-xl border border-outline-variant bg-surface-container-low text-[13px] outline-none transition-all focus:border-brand focus:bg-white focus:shadow-[0_0_0_3px_rgba(59,130,246,0.08)]"
            :disabled="isThinking"
            @keyup.enter="sendMessage"
          />
        </div>
        <button
          class="w-10 h-10 rounded-xl flex items-center justify-center bg-brand text-white shadow-soft hover:shadow-glow hover:-translate-y-px transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none"
          :disabled="!input.trim() || isThinking"
          @click="sendMessage"
        >
          <el-icon v-if="isThinking" :size="16" class="is-loading"><Loading /></el-icon>
          <el-icon v-else :size="16"><Promotion /></el-icon>
        </button>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2.5">
        <button class="btn-cancel" @click="handleClose">{{ t('agentBuilder.cancel') }}</button>
        <button
          class="btn-create"
          :class="{ 'btn-create-disabled': !draft }"
          :disabled="!draft"
          @click="confirmDraft"
        >
          {{ t('agentBuilder.useAgent') }}
        </button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { User, MagicStick, Loading, Promotion } from '@element-plus/icons-vue'
import type { AgentDraft } from '@/types/agent'
import { agentsApi } from '@/api/agents'
import type { AgentBuildDraft } from '@/api/agents'

const { t } = useI18n()

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
    content: t('agentBuilder.greetingInitial'),
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
      content: t('agentBuilder.greetingSimple'),
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
      content: t('agentBuilder.draftConfirmation', { name: result.draft.name }),
    })
  } catch {
    messages.value.push({
      id: String(Date.now() + 1),
      role: 'assistant',
      content: t('agentBuilder.errorGeneration'),
    })
    ElMessage.error(t('agentBuilder.errorBuildFailed'))
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

<style>
/* Dialog Override */
.agent-builder-dialog .el-dialog__header {
  padding: 20px 24px 0 !important;
  margin-right: 0 !important;
  border-bottom: none !important;
}
.agent-builder-dialog .el-dialog__body {
  padding: 16px 24px !important;
}
.agent-builder-dialog .el-dialog__footer {
  padding: 0 24px 20px !important;
  border-top: none !important;
}
</style>
