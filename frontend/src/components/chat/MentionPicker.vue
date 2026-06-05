<template>
  <div
    class="absolute z-50 bg-white border border-outline-variant rounded-xl shadow-float py-1.5 w-56 max-h-48 overflow-y-auto custom-scrollbar"
    :style="{ bottom: '100%', left: position.left + 'px', marginBottom: '4px' }"
  >
    <div v-if="filteredAgents.length === 0" class="px-3 py-2 text-[12px] text-on-surface-variant">
      No agents found
    </div>
    <div
      v-for="(agent, i) in filteredAgents"
      :key="agent.id"
      class="flex items-center gap-2.5 px-3 py-2 mx-1 rounded-lg cursor-pointer text-[13px] transition-colors"
      :class="i === activeIndex ? 'bg-brand-light/50 text-brand' : 'hover:bg-surface-container text-on-surface'"
      @mousedown.prevent
      @click="onSelect(agent)"
      @mouseenter="activeIndex = i"
    >
      <div class="w-6 h-6 rounded-md bg-brand-light flex items-center justify-center text-brand text-[10px] font-bold shrink-0 overflow-hidden">
        <img v-if="agent.avatar" :src="agent.avatar" :alt="agent.name" class="w-full h-full object-cover" />
        <span v-else>{{ agent.name.charAt(0) }}</span>
      </div>
      <div class="min-w-0">
        <p class="font-medium truncate">{{ agent.name }}</p>
        <p class="text-[10px] text-on-surface-variant truncate">{{ agent.role }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { ChatAgent } from '@/types/chat'

const props = defineProps<{
  agents: ChatAgent[]
  query: string
  position: { top: number; left: number }
}>()

const emit = defineEmits<{
  select: [agent: ChatAgent]
  dismiss: []
}>()

const activeIndex = ref(0)

const filteredAgents = computed(() => {
  if (!props.query) return props.agents
  const q = props.query.toLowerCase()
  return props.agents.filter(a =>
    a.name.toLowerCase().includes(q) ||
    a.role.toLowerCase().includes(q)
  )
})

watch(() => props.query, () => { activeIndex.value = 0 })

function onSelect(agent: ChatAgent) {
  emit('select', agent)
}

function navigate(direction: 1 | -1) {
  const max = filteredAgents.value.length - 1
  activeIndex.value = Math.max(0, Math.min(max, activeIndex.value + direction))
}

function confirmSelection() {
  const agent = filteredAgents.value[activeIndex.value]
  if (agent) emit('select', agent)
}

defineExpose({ navigate, confirmSelection })
</script>
