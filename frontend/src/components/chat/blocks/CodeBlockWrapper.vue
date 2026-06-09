<template>
  <CollapsibleBlock
    :label="filename || t('codeBlockExtra.defaultLabel')"
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
        {{ t('codeBlock.preview') }}
      </button>
      <button
        v-if="oldCode && messageId"
        class="text-[10px] font-medium px-2 py-0.5 rounded transition-colors"
        :class="applyState === 'loading'
          ? 'opacity-50 cursor-not-allowed text-neutral-400'
          : applyState === 'done'
            ? 'cursor-pointer text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50'
            : applyState === 'error'
              ? 'cursor-pointer text-red-500 hover:bg-red-50'
              : 'cursor-pointer text-brand hover:text-brand-dark hover:bg-brand-light'"
        :disabled="applyState === 'loading'"
        @click.stop="handleApply"
      >
        {{ applyLabel }}
      </button>
      <button
        class="text-[10px] text-neutral-500 hover:text-neutral-700 transition-colors px-1.5 py-0.5 rounded hover:bg-neutral-200 cursor-pointer"
        @click.stop="handleCopy"
      >
        {{ copied ? t('codeBlock.copied') : t('codeBlock.copy') }}
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
import { useI18n } from 'vue-i18n'
import { Document } from '@element-plus/icons-vue'
import CollapsibleBlock from './CollapsibleBlock.vue'
import CodeBlock from '../CodeBlock.vue'
import { useArtifactPreview } from '@/composables/useArtifactPreview'
import { artifactsApi } from '@/api/artifacts'

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

const { t } = useI18n()
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

type ApplyState = 'idle' | 'loading' | 'done' | 'error'
const applyState = ref<ApplyState>('idle')

const applyLabel = computed(() => {
  switch (applyState.value) {
    case 'loading': return t('codeBlock.applying')
    case 'done': return t('codeBlock.applied')
    case 'error': return t('codeBlock.failed')
    default: return t('codeBlock.apply')
  }
})

async function handleApply() {
  if (!props.messageId || applyState.value === 'loading') return
  applyState.value = 'loading'
  try {
    const editedCode = codeBlockRef.value?.editableCode
    await artifactsApi.applyDiff(props.messageId, editedCode)
    applyState.value = 'done'
  } catch {
    applyState.value = 'error'
    setTimeout(() => { applyState.value = 'idle' }, 3000)
  }
}
</script>
