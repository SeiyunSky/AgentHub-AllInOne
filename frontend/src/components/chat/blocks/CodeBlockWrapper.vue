<template>
  <CollapsibleBlock
    :label="filename || 'Code'"
    :icon="Document"
    variant="code"
    :badge="language"
    :default-expanded="defaultExpanded"
  >
    <CodeBlock
      :code="code"
      :filename="filename"
      :language="language"
      :old-code="oldCode"
    />
  </CollapsibleBlock>
</template>

<script setup lang="ts">
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
</script>