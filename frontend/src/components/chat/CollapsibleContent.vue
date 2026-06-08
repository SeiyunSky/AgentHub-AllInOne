<script setup lang="ts">
import { shallowRef, computed, onMounted, onUnmounted, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'

const props = withDefaults(defineProps<{
  maxHeight?: number
  /** 渐变遮罩的起始颜色，需与父背景色一致 */
  gradientFrom?: string
  /** streaming 期间强制展开，不截断 */
  streaming?: boolean
}>(), {
  maxHeight: 800,
  gradientFrom: '#ffffff',
  streaming: false,
})

const contentRef = useTemplateRef<HTMLDivElement>('content')
const expanded = shallowRef(false)
const overflows = shallowRef(false)

let ro: ResizeObserver | null = null

onMounted(() => {
  ro = new ResizeObserver(() => {
    if (contentRef.value) {
      overflows.value = contentRef.value.scrollHeight > props.maxHeight
    }
  })
  if (contentRef.value) ro.observe(contentRef.value)
})

onUnmounted(() => {
  ro?.disconnect()
})

const containerStyle = computed(() => {
  if (props.streaming || expanded.value || !overflows.value) return {}
  return { maxHeight: `${props.maxHeight}px`, overflow: 'hidden' }
})

const gradientStyle = computed(() => ({
  background: `linear-gradient(to bottom, transparent, ${props.gradientFrom})`,
}))

const isCollapsed = computed(() => overflows.value && !expanded.value && !props.streaming)

const { t } = useI18n()
</script>

<template>
  <div class="collapsible-content" :style="containerStyle">
    <div ref="content">
      <slot />
    </div>

    <!-- 底部渐变遮罩 -->
    <div v-if="isCollapsed" class="gradient-mask" :style="gradientStyle" />
  </div>

  <!-- 展开/收起栏，放在容器外部避免被 overflow:hidden 裁切 -->
  <div v-if="overflows && !streaming" class="toggle-bar">
    <button class="toggle-btn" @click="expanded = !expanded">
      <svg
        class="toggle-icon"
        :class="{ 'is-expanded': expanded }"
        viewBox="0 0 16 16"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span>{{ expanded ? t('collapsible.collapse') : t('collapsible.expandAll') }}</span>
    </button>
  </div>
</template>

<style scoped>
.collapsible-content {
  position: relative;
  transition: max-height 0.3s ease;
}

.gradient-mask {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 80px;
  pointer-events: none;
}

.toggle-bar {
  display: flex;
  justify-content: center;
  margin-top: 6px;
}

.toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 500;
  color:  #666;
  background: rgba(0,0,0,0.02);
  border-radius: 999px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s;
}

.toggle-btn:hover {
  background: rgba(0,0,0,0.05);
  color: #1c1c1c;
}

.toggle-icon {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.toggle-icon.is-expanded {
  transform: rotate(180deg);
}
</style>
