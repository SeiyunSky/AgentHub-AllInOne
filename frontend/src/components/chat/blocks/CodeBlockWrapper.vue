<template>
  <CollapsibleBlock
    :label="filename || 'Code'"
    :icon="Document"
    variant="code"
    :badge="language"
    :default-expanded="defaultExpanded"
  >
    <template #actions>
      <button
        class="text-[10px] text-neutral-500 hover:text-neutral-700 transition-colors px-1.5 py-0.5 rounded hover:bg-neutral-200 cursor-pointer"
        @click.stop="handleCopy"
      >
        {{ copied ? 'Copied!' : 'Copy' }}
      </button>
    </template>
    <CodeBlock
      ref="codeBlockRef"
      :code="code"
      :filename="filename"
      :language="language"
      :old-code="oldCode"
    />
  </CollapsibleBlock>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Document } from '@element-plus/icons-vue'
import CollapsibleBlock from './CollapsibleBlock.vue'
import CodeBlock from '../CodeBlock.vue'

withDefaults(defineProps<{
  code: string
  filename?: string
  language?: string
  oldCode?: string
  defaultExpanded?: boolean
}>(), {
  defaultExpanded: true,
})

const codeBlockRef = ref<InstanceType<typeof CodeBlock>>()
const copied = ref(false)

async function handleCopy() {
  await codeBlockRef.value?.handleCopy()
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}
</script>