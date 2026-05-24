<template>
  <div class="rounded-xl overflow-hidden border border-neutral-800">
    <!-- Header -->
    <div class="bg-neutral-900 px-3 py-1.5 flex items-center gap-3 border-b border-neutral-800">
      <div class="flex gap-1.5">
        <span class="w-2.5 h-2.5 rounded-full bg-red-500/80"></span>
        <span class="w-2.5 h-2.5 rounded-full bg-yellow-500/80"></span>
        <span class="w-2.5 h-2.5 rounded-full bg-green-500/80"></span>
      </div>
      <span class="text-[10px] text-neutral-400 font-mono">{{ filename }}</span>
      <span v-if="language" class="text-[9px] text-neutral-500 px-1.5 py-0.5 rounded bg-neutral-800">{{ language }}</span>
      <div class="flex-1" />
      <button
        class="text-[10px] text-neutral-500 hover:text-neutral-300 transition-colors px-1.5 py-0.5 rounded hover:bg-neutral-800 cursor-pointer"
        @click="handleCopy"
      >
        {{ copied ? 'Copied!' : 'Copy' }}
      </button>
    </div>

    <!-- Code content -->
    <div class="bg-neutral-900/95 text-xs font-mono leading-[1.6] overflow-x-auto">
      <!-- Diff view -->
      <template v-if="diffLines.length > 0">
        <div
          v-for="(line, i) in diffLines"
          :key="i"
          class="flex items-stretch"
          :class="lineClass(line.type)"
        >
          <!-- Old line number -->
          <span class="w-8 text-right px-2 text-neutral-600 select-none shrink-0 bg-neutral-900/50" :class="{ 'opacity-50': line.type === 'added' }">
            {{ line.oldNum ?? '' }}
          </span>
          <!-- New line number -->
          <span class="w-8 text-right px-2 text-neutral-600 select-none shrink-0 border-l border-neutral-800" :class="{ 'opacity-50': line.type === 'removed' }">
            {{ line.newNum ?? '' }}
          </span>
          <!-- Diff marker -->
          <span class="w-5 text-center select-none shrink-0" :class="markerClass(line.type)">
            {{ line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' ' }}
          </span>
          <!-- Content -->
          <pre class="px-2 flex-1 whitespace-pre" :class="contentClass(line.type)">{{ line.content }}</pre>
        </div>
      </template>

      <!-- Regular code view -->
      <template v-else>
        <div
          v-for="(line, i) in codeLines"
          :key="i"
          class="flex items-stretch hover:bg-neutral-800/30"
        >
          <span class="w-8 text-right px-2 text-neutral-600 select-none shrink-0">{{ i + 1 }}</span>
          <span class="w-5 text-center text-neutral-700 select-none shrink-0">│</span>
          <pre class="px-2 flex-1 whitespace-pre text-slate-300">{{ line }}</pre>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import * as Diff from 'diff'

const props = defineProps<{
  code: string
  filename?: string
  language?: string
  oldCode?: string  // For diff view - original code
}>()

const codeLines = computed(() => props.code.split('\n'))

const diffLines = computed(() => {
  if (!props.oldCode) return []

  const patch = Diff.createPatch('', props.oldCode, props.code, '', '')
  const patchLines = patch.split('\n').slice(4) // Skip header lines

  let oldNum = 0
  let newNum = 0
  const result: Array<{
    type: 'added' | 'removed' | 'context'
    content: string
    oldNum?: number
    newNum?: number
  }> = []

  for (const line of patchLines) {
    if (line.startsWith('@@')) {
      // Parse hunk header: @@ -oldStart,oldCount +newStart,newCount @@
      const match = line.match(/@@ -(\d+),?\d* \+(\d+),?\d* @@/)
      if (match) {
        oldNum = parseInt(match[1])
        newNum = parseInt(match[2])
      }
      continue
    }

    if (line.startsWith('+')) {
      result.push({ type: 'added', content: line.slice(1), newNum })
      newNum++
    } else if (line.startsWith('-')) {
      result.push({ type: 'removed', content: line.slice(1), oldNum })
      oldNum++
    } else if (line.startsWith(' ')) {
      result.push({ type: 'context', content: line.slice(1), oldNum, newNum })
      oldNum++
      newNum++
    }
  }

  return result
})

function lineClass(type: string) {
  switch (type) {
    case 'added': return 'bg-emerald-900/30'
    case 'removed': return 'bg-red-900/30'
    default: return ''
  }
}

function markerClass(type: string) {
  switch (type) {
    case 'added': return 'text-emerald-400'
    case 'removed': return 'text-red-400'
    default: return 'text-neutral-700'
  }
}

function contentClass(type: string) {
  switch (type) {
    case 'added': return 'text-emerald-300'
    case 'removed': return 'text-red-300'
    default: return 'text-slate-300'
  }
}

const copied = ref(false)

async function handleCopy() {
  try {
    await navigator.clipboard.writeText(props.code)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = props.code
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}
</script>