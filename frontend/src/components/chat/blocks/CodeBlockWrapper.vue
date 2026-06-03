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
        v-if="canPreview"
        class="text-[10px] text-brand hover:text-brand/80 transition-colors px-1.5 py-0.5 rounded hover:bg-brand/10 cursor-pointer"
        @click.stop="openPreview"
      >
        Preview
      </button>
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
import { ref, computed } from 'vue'
import { Document } from '@element-plus/icons-vue'
import CollapsibleBlock from './CollapsibleBlock.vue'
import CodeBlock from '../CodeBlock.vue'
import { useArtifactPreview } from '@/composables/useArtifactPreview'

const props = withDefaults(defineProps<{
  code: string
  filename?: string
  language?: string
  oldCode?: string
  defaultExpanded?: boolean
  messageId?: string
}>(), {
  defaultExpanded: true,
})

const codeBlockRef = ref<InstanceType<typeof CodeBlock>>()
const copied = ref(false)
const { openArtifact } = useArtifactPreview()

const canPreview = computed(() =>
  !!props.messageId && ['html', 'svg'].includes((props.language ?? '').toLowerCase())
)

function openPreview() {
  if (!props.messageId) return
  const lang = (props.language ?? '').toLowerCase()
  openArtifact(props.messageId, {
    name: props.filename || `preview.${lang}`,
    type: lang,
    mimeType: lang === 'svg' ? 'image/svg+xml' : 'text/html',
    preview: props.code,
  }, 0)
}

async function handleCopy() {
  await codeBlockRef.value?.handleCopy()
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}
</script>