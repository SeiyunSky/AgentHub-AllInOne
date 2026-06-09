<template>
  <div
    v-if="!(streaming && (!message.blocks || message.blocks.length === 0))"
    class="flex gap-3 message-enter group mb-5"
  >
    <div
      class="w-9 h-9 rounded-[20%] flex items-center justify-center shrink-0 overflow-hidden"
    >
      <img v-if="agentAvatar" :src="agentAvatar" :alt="displayAgentName" class="w-full h-full object-cover" />
    </div>

    <div class="flex-1 min-w-0 relative pb-5">
      <!-- Header -->
      <div class="flex items-center gap-2 mb-1.5">
        <span class="text-[12px] font-semibold text-on-surface">{{ displayAgentName }}</span>
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

      <CollapsibleContent :streaming="streaming">
        <!-- Blocks mode -->
        <div v-if="message.blocks && message.blocks.length > 0" class="space-y-2">
          <!-- Text block -->
          <div v-for="(block, i) in displayBlocks" :key="i">
            <div v-if="block.type === 'text'" class="text-block">
              <MarkdownRenderer class="text-[13px] leading-relaxed text-on-surface" :content="block.content" />
              <StreamingCursor v-if="(streaming && i === (displayBlocks?.length ?? 0) - 1) || (!typewriterDone && i === (displayBlocks?.length ?? 0) - 1)" />
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
              :message-id="message.id"
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

            <!-- Meme block -->
            <div
              v-else-if="block.type === 'meme'"
              class="meme-block"
            >
              <img
                :src="(block as any).url"
                :alt="(block as any).description"
                class="max-w-[200px] max-h-[200px] rounded-xl object-contain"
                :title="(block as any).description"
              />
            </div>

            <!-- Approval block -->
            <ApprovalBlock
              v-else-if="block.type === 'approval'"
              :message-id="message.id"
              :block-id="(block as any).blockId"
              :action="(block as any).action"
              :detail="(block as any).detail"
              :status="(block as any).status"
              :decided-at="(block as any).decidedAt"
              :reject-reason="(block as any).rejectReason"
            />
          </div>
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
      </CollapsibleContent>

      <!-- Actions -->
      <MessageActions
        :message-id="message.id"
        variant="agent"
        :content="messageContent"
        :reaction="message.reaction"
        @reply="$emit('reply', $event)"
        @copy="$emit('copy', $event)"
        @react="(id, type) => $emit('react', id, type)"
      />

      <!-- Persistent reaction badge -->
      <div
        v-if="message.reaction"
        class="px-1 py-1.5 rounded-md bg-neutral-100 text-[14px] leading-none select-none inline-flex items-center gap-1 w-fit"
        :title="message.reaction === 'like' ? t('agentBubble.reactionLike') : t('agentBubble.reactionDislike')"
      >{{ message.reaction === 'like' ? '😀' : '🙁' }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AgentMessage } from '@/types/chat'
import { useAgentsStore } from '@/stores/agents'
import { useChatStore } from '@/stores/chat'
import MarkdownRenderer from '@/components/common/MarkdownRenderer.vue'
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
import CollapsibleContent from '../CollapsibleContent.vue'

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
}>()

const { t } = useI18n()
const agentsStore = useAgentsStore()
const chatStore = useChatStore()
// 进入气泡时确保 agents store 已加载（幂等，重复调直接返回）
agentsStore.loadAgents()

// ── broadcast 打字流动画 ──
// displayBlocks 是实际渲染用的 blocks 副本；typewriterDone 控制是否显示全文
const displayBlocks = ref<typeof props.message.blocks>(props.message.blocks)
const typewriterDone = ref(true)

function startTypewriter() {
  const textBlockIdx = props.message.blocks?.findIndex(b => b.type === 'text') ?? -1
  if (textBlockIdx === -1 || !props.message.blocks) return

  const fullText = (props.message.blocks[textBlockIdx] as { content: string }).content
  if (!fullText) return

  typewriterDone.value = false

  // 克隆 blocks，把 text block 内容先清空
  const cloned = props.message.blocks.map((b, i) =>
    i === textBlockIdx ? { ...b, content: '' } : { ...b }
  )
  displayBlocks.value = cloned as typeof props.message.blocks

  let pos = 0
  const CHARS_PER_TICK = 2
  const TICK_MS = 40

  const timer = setInterval(() => {
    pos += CHARS_PER_TICK
    ;(cloned[textBlockIdx] as { content: string }).content = fullText.slice(0, pos)
    displayBlocks.value = [...cloned] as typeof props.message.blocks

    if (pos >= fullText.length) {
      clearInterval(timer)
      ;(cloned[textBlockIdx] as { content: string }).content = fullText
      displayBlocks.value = props.message.blocks
      typewriterDone.value = true
    }
  }, TICK_MS)
}

// 用 watch 代替 onMounted：streaming bubble 被复用时 onMounted 不会再触发，
// 而 commitAgentStreaming 写入 newBroadcastMessageIds 后 watch 能检测到变化。
watch(
  () => chatStore.newBroadcastMessageIds.has(props.message.id),
  (isNew) => {
    if (!isNew) return
    chatStore.consumeNewBroadcastMessage(props.message.id)
    startTypewriter()
  },
  { immediate: true },
)

// 非动画状态下跟随 props 更新 displayBlocks（streaming 期间 blocks 实时增量）
watch(
  () => props.message.blocks,
  (blocks) => {
    if (typewriterDone.value) {
      displayBlocks.value = blocks
    }
  },
)

const agentAvatar = computed(() =>
  agentsStore.agents.find(a => a.id === props.message.agentId)?.avatar ?? props.message.avatar
)

const displayAgentName = computed(() => {
  // 数据库 agent.name 是真相源；message.agentName 是 SSE 事件携带的快照值，
  // 两者不一致时优先用 store 里的 name（避免 streaming 期"主 Agent" → commit 后"Orchestrator"切换）
  const stored = agentsStore.agents.find(a => a.id === props.message.agentId)?.name
  return stored ?? props.message.agentName
})

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
    case 'thinking': return t('agentBubble.thinking')
    case 'typing': return t('agentBubble.typing')
    case 'tool':
      return props.currentTool ? `${t('agentBubble.toolPrefix')} ${props.currentTool}` : t('agentBubble.toolFallback')
    case 'idle': return t('agentBubble.idle')
    default: return t('agentBubble.typing')
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
  if (minutes < 1) return t('timeAgo.justNow')
  if (minutes < 60) return t('timeAgo.minutesAgo', { n: minutes })
  return t('timeAgo.hoursAgo', { n: Math.floor(minutes / 60) })
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