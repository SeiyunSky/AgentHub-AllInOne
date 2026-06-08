<template>
  <CollapsibleBlock
    :label="label"
    :icon="MagicStick"
    variant="thinking"
    :meta="durationText"
    :default-expanded="defaultExpanded"
  >
    <div class="px-3 py-2 text-[13px] text-purple-600/80 leading-relaxed whitespace-pre-wrap italic">
      {{ content }}
    </div>
  </CollapsibleBlock>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { MagicStick } from '@element-plus/icons-vue'
import CollapsibleBlock from './CollapsibleBlock.vue'

const props = withDefaults(defineProps<{
  content: string
  duration?: number
  defaultExpanded?: boolean
}>(), {
  defaultExpanded: false,
})

const { t } = useI18n()

const label = computed(() => t('thinking.label'))

const durationText = computed(() => {
  if (!props.duration) return ''
  const seconds = Math.floor(props.duration / 1000)
  if (seconds < 1) return `${props.duration}ms`
  return `${seconds}s`
})
</script>
