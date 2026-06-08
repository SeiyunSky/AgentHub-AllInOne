<script setup lang="ts">
import { computed, watch } from 'vue'
import { RouterView } from 'vue-router'
import { ElConfigProvider } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import elEn from 'element-plus/es/locale/lang/en'
import { useThemeStore } from '@/stores/theme'
import { applyLang } from '@/i18n'

const themeStore = useThemeStore()
const elLocale = computed(() => themeStore.lang === 'zh' ? zhCn : elEn)

// 同步 theme.lang → vue-i18n locale
watch(() => themeStore.lang, (lang) => applyLang(lang), { immediate: true })
</script>

<template>
  <ElConfigProvider :locale="elLocale">
    <RouterView />
  </ElConfigProvider>
</template>
