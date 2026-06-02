<template>
  <div class="flex gap-3 message-enter group">
    <AgentAvatar :name="message.agentName" :color="avatarColor" :avatar="agentAvatar" />

    <div class="flex-1 min-w-0 relative pb-3">
      <!-- Header -->
      <div class="flex items-center gap-2 mb-1.5">
        <span class="text-[12px] font-semibold text-on-surface">{{ message.agentName }}</span>
        <span
          v-if="message.agentRole"
          class="text-[10px] font-semibold px-2 py-0.5 rounded-md uppercase"
          :class="roleBadgeClass"
        >{{ message.agentRole }}</span>

        <!-- Streaming activity chip:streaming 中显示当前在干啥 -->
        <span
          v-if="streaming"
          class="text-[10px] font-medium px-2 py-0.5 rounded-md inline-flex items-center gap-1"
          :class="activityChipClass"
        >
          <span class="activity-dot" :class="activityDotClass"></span>
          {{ activityLabel }}
        </span>

        <span class="text-[10px] text-on-surface-variant">{{ timeAgo }}</span>
      </div>

      <!-- Blocks mode -->
      <div v-if="message.blocks && message.blocks.length > 0" class="space-y-2">
        <!-- Text block -->
        <div v-for="(block, i) in message.blocks" :key="i">
          <div v-if="block.type === 'text'" class="text-block">
            <MarkdownRenderer class="text-[13px] leading-relaxed text-on-surface" :content="block.content" />
            <StreamingCursor v-if="streaming && i === message.blocks.length - 1" />
          </div>

          <!-- Thinking block -->
          <ThinkingBlock
            v-else-if="block.type === 'thinking'"
            :content="block.content"
            :duration="block.duration"
          />

          <!-- Tool use block -->
          <ToolUseBlock
            v-else-if="block.type === 'tool_use'"
            :tool-name="block.toolName"
            :input="block.input"
            :output="block.output"
            :status="block.status"
          />

          <!-- Code block -->
          <CodeBlockWrapper
            v-else-if="block.type === 'code'"
            :code="block.code"
            :filename="block.filename"
            :language="block.language"
            :old-code="block.oldCode"
          />

          <!-- Deployment block -->
          <DeploymentBlock
            v-else-if="block.type === 'deployment'"
            :title="block.title"
            :status="block.status"
            :url="block.url"
            :logs="block.logs"
            :progress="block.progress"
          />

          <!-- Image block -->
          <ImageBlock
            v-else-if="block.type === 'image'"
            :src="block.src"
            :alt="block.alt"
            :caption="block.caption"
          />

          <!-- Artifacts block -->
          <ArtifactsBlock
            v-else-if="block.type === 'artifacts'"
            :message-id="message.id"
            :artifact="block.item"
          />

          <!-- Approval block -->
          <ApprovalBlock
            v-else-if="block.type === 'approval'"
            :action="block.action"
            :detail="block.detail"
            :status="block.status"
            :decided-at="block.decidedAt"
            :reject-reason="block.rejectReason"
          />
        </div>
      </div>

      <!-- Streaming: blocks empty, show typing indicator -->
      <div v-else-if="streaming" class="p-4 bg-white border border-outline-variant rounded-2xl rounded-tl-md shadow-soft inline-flex items-center gap-1.5">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </div>

      <!-- Legacy mode: single content + optional codeBlock -->
      <template v-else>
        <div class="text-block">
          <MarkdownRenderer class="text-[13px] leading-relaxed text-on-surface" :content="message.content" />

          <CodeBlock
            v-if="message.codeBlock"
            class="mt-3"
            :code="message.codeBlock.code"
            :filename="message.codeBlock.filename"
            :language="message.codeBlock.language"
            :old-code="message.codeBlock.oldCode"
          />
        </div>
      </template>

      <!-- Actions -->
      <MessageActions
        :message-id="message.id"
        variant="agent"
        :content="messageContent"
        :reaction="message.reaction"
        @reply="$emit('reply', $event)"
        @copy="$emit('copy', $event)"
        @react="(id, type) => $emit('react', id, type)"
        @more="$emit('more', $event)"
      />

      <!-- Persistent reaction badge -->
      <div
        v-if="message.reaction"
        class="absolute -bottom-2 left-1 text-[13px] leading-none select-none"
        :title="message.reaction === 'like' ? '已点赞' : '已点踩'"
      >{{ message.reaction === 'like' ? '😀' : '🙁' }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AgentMessage } from '@/types/chat'
import { useAgentsStore } from '@/stores/agents'
import MarkdownRenderer from '@/components/common/MarkdownRenderer.vue'
import AgentAvatar from './AgentAvatar.vue'
import StreamingCursor from './StreamingCursor.vue'
import CodeBlock from '../CodeBlock.vue'
import MessageActions from '../MessageActions.vue'
import ThinkingBlock from '../blocks/ThinkingBlock.vue'
import ToolUseBlock from '../blocks/ToolUseBlock.vue'
import CodeBlockWrapper from '../blocks/CodeBlockWrapper.vue'
import DeploymentBlock from '../blocks/DeploymentBlock.vue'
import ImageBlock from '../blocks/ImageBlock.vue'
import ArtifactsBlock from '../blocks/ArtifactsBlock.vue'
import ApprovalBlock from '../blocks/ApprovalBlock.vue'

const props = defineProps<{
  message: AgentMessage
  streaming?: boolean
  /** streaming 时当前活跃状态:thinking/typing/tool/idle */
  activity?: 'thinking' | 'typing' | 'tool' | 'idle'
  /** activity=tool 时正在调用的工具名 */
  currentTool?: string
}>()

defineEmits<{
  reply: [messageId: string]
  copy: [messageId: string]
  react: [messageId: string, type: 'like' | 'dislike']
  more: [messageId: string]
}>()

const avatarColor = computed(() => props.message.agentRoleColor ?? 'brand')

const agentsStore = useAgentsStore()
const agentAvatar = computed(() =>
  agentsStore.agents.find(a => a.id === props.message.agentId)?.avatar ?? props.message.avatar
)

const messageContent = computed(() => {
  if (props.message.blocks && props.message.blocks.length > 0) {
    return props.message.blocks
      .filter(b => b.type === 'text')
      .map(b => b.content)
      .join('\n')
  }
  return props.message.content
})

const roleBadgeClass = computed(() => {
  switch (props.message.agentRoleColor) {
    case 'warning': return 'bg-warning-light text-amber-700'
    case 'success': return 'bg-success-light text-success'
    case 'error': return 'bg-error-light text-error'
    default: return 'bg-brand-light text-brand'
  }
})

const activityLabel = computed(() => {
  switch (props.activity) {
    case 'thinking': return '思考中'
    case 'typing': return '回复中'
    case 'tool':
      return props.currentTool ? `调用 ${props.currentTool}` : '调用工具'
    case 'idle': return '等待中'
    default: return '回复中'
  }
})

const activityChipClass = computed(() => {
  switch (props.activity) {
    case 'thinking': return 'bg-purple-50 text-purple-600'
    case 'typing': return 'bg-brand-light text-brand'
    case 'tool': return 'bg-amber-50 text-amber-700'
    case 'idle': return 'bg-surface-container text-on-surface-variant'
    default: return 'bg-brand-light text-brand'
  }
})

const activityDotClass = computed(() => {
  switch (props.activity) {
    case 'thinking': return 'bg-purple-500'
    case 'typing': return 'bg-brand'
    case 'tool': return 'bg-amber-500'
    case 'idle': return 'bg-on-surface-variant'
    default: return 'bg-brand'
  }
})

const timeAgo = computed(() => {
  const now = new Date()
  const diff = now.getTime() - props.message.timestamp.getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  return `${Math.floor(minutes / 60)}h ago`
})
</script>

<style scoped>
.activity-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  animation: activity-pulse 1.2s ease-in-out infinite;
}

@keyframes activity-pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50%      { opacity: 1;   transform: scale(1.1); }
}
</style>