<template>
  <div class="flex gap-3 message-enter">
    <AgentAvatar :name="message.agentName" :color="avatarColor" />

    <div class="flex-1 min-w-0">
      <!-- Header -->
      <div class="flex items-center gap-2 mb-1.5">
        <span class="text-[12px] font-semibold text-on-surface">{{ message.agentName }}</span>
        <span
          v-if="message.agentRole"
          class="text-[10px] font-semibold px-2 py-0.5 rounded-md uppercase"
          :class="roleBadgeClass"
        >{{ message.agentRole }}</span>
        <span class="text-[10px] text-on-surface-variant">{{ timeAgo }}</span>
      </div>

      <!-- Blocks mode -->
      <div v-if="message.blocks && message.blocks.length > 0" class="space-y-2">
        <!-- Text block -->
        <div v-for="(block, i) in message.blocks" :key="i">
          <div v-if="block.type === 'text'" class="p-4 bg-white border border-outline-variant rounded-2xl rounded-tl-md shadow-soft">
            <p class="text-[13px] leading-relaxed text-on-surface whitespace-pre-wrap">{{ block.content }}</p>
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
            :title="block.title"
            :items="block.items"
          />
        </div>
      </div>

      <!-- Legacy mode: single content + optional codeBlock -->
      <template v-else>
        <div class="p-4 bg-white border border-outline-variant rounded-2xl rounded-tl-md shadow-soft">
          <p class="text-[13px] leading-relaxed text-on-surface whitespace-pre-wrap">{{ message.content }}</p>

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
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AgentMessage } from '@/types/chat'
import AgentAvatar from './AgentAvatar.vue'
import CodeBlock from '../CodeBlock.vue'
import ThinkingBlock from '../blocks/ThinkingBlock.vue'
import ToolUseBlock from '../blocks/ToolUseBlock.vue'
import CodeBlockWrapper from '../blocks/CodeBlockWrapper.vue'
import DeploymentBlock from '../blocks/DeploymentBlock.vue'
import ImageBlock from '../blocks/ImageBlock.vue'
import ArtifactsBlock from '../blocks/ArtifactsBlock.vue'

const props = defineProps<{
  message: AgentMessage
}>()

const avatarColor = computed(() => props.message.agentRoleColor ?? 'brand')

const roleBadgeClass = computed(() => {
  switch (props.message.agentRoleColor) {
    case 'warning': return 'bg-warning-light text-amber-700'
    case 'success': return 'bg-success-light text-success'
    case 'error': return 'bg-error-light text-error'
    default: return 'bg-brand-light text-brand'
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