<template>
  <CollapsibleBlock
    :label="artifact.name"
    :icon="Files"
    variant="artifact"
    :badge="artifact.type"
    :default-expanded="defaultExpanded"
  >
    <CodeBlock :code="artifact.preview ?? ''" :filename="artifact.name" :language="artifact.type" />

    <template #actions>
      <el-button
        v-if="artifact.preview"
        text
        size="small"
        class="!text-[11px] !text-brand"
        @click.stop="openPreview"
      >
        Preview
      </el-button>
    </template>
  </CollapsibleBlock>
</template>

<script setup lang="ts">
import { Files } from '@element-plus/icons-vue'
import CollapsibleBlock from './CollapsibleBlock.vue'
import CodeBlock from '../CodeBlock.vue'
import { useArtifactPreview } from '@/composables/useArtifactPreview'
import type { ArtifactItem } from '@/types/artifact'

const props = withDefaults(defineProps<{
  messageId: string
  artifact: ArtifactItem
  defaultExpanded?: boolean
}>(), {
  defaultExpanded: true,
})

const { openArtifact } = useArtifactPreview()

function openPreview() {
  openArtifact(props.messageId, props.artifact, 0)
}
</script>
