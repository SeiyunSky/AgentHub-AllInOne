<template>
  <CollapsibleBlock
    :label="caption || t('imageBlock.defaultLabel')"
    :icon="Picture"
    variant="image"
    :default-expanded="defaultExpanded"
  >
    <div class="px-3 py-2">
      <div class="rounded-lg overflow-hidden bg-slate-50">
        <img
          :src="src"
          :alt="alt || caption || t('imageBlock.defaultAlt')"
          class="w-full max-h-64 object-cover"
        />
      </div>
      <p v-if="caption" class="mt-1.5 text-[11px] text-on-surface-variant">{{ caption }}</p>
    </div>
  </CollapsibleBlock>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Picture } from '@element-plus/icons-vue'
import CollapsibleBlock from './CollapsibleBlock.vue'

const { t } = useI18n()

withDefaults(defineProps<{
  src: string
  alt?: string
  caption?: string
  defaultExpanded?: boolean
}>(), {
  defaultExpanded: true,
})
</script>
