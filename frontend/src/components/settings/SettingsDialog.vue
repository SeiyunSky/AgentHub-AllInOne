<template>
  <Teleport to="body">
    <Transition name="overlay-fade">
      <div
        v-if="visible"
        class="fixed inset-0 z-[300] flex items-center justify-center"
        style="background: rgba(0,0,0,0.5); backdrop-filter: blur(4px);"
        @click.self="close"
      >
        <Transition name="dialog-pop">
          <div
            v-if="visible"
            class="w-[480px] max-h-[80vh] overflow-y-auto rounded-2xl shadow-float border border-outline-variant custom-scrollbar"
            style="background: var(--color-surface-elevated, #fff);"
          >
            <!-- Header -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-outline-variant">
              <div class="flex items-center gap-2.5">
                <div class="w-7 h-7 rounded-lg flex items-center justify-center" style="background: color-mix(in srgb, var(--color-brand) 12%, transparent);">
                  <el-icon :size="15" style="color: var(--color-brand)"><Setting /></el-icon>
                </div>
                <span class="text-[15px] font-semibold text-on-surface">{{ t('settings.title') }}</span>
              </div>
              <button
                class="w-7 h-7 rounded-lg flex items-center justify-center text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-all"
                @click="close"
              >
                <el-icon :size="16"><Close /></el-icon>
              </button>
            </div>

            <!-- Body -->
            <div class="px-6 py-5 space-y-7">

              <!-- Accent color -->
              <section>
                <div class="section-heading">
                  <el-icon :size="12"><Brush /></el-icon>
                  {{ t('settings.accentColor') }}
                </div>
                <div class="grid grid-cols-6 gap-2.5">
                  <button
                    v-for="acc in ACCENTS"
                    :key="acc.key"
                    class="accent-btn"
                    :class="{ active: themeStore.accent === acc.key }"
                    :title="acc.label"
                    @click="themeStore.setAccent(acc.key)"
                  >
                    <div
                      class="accent-dot"
                      :style="{ background: acc.color }"
                    >
                      <el-icon v-if="themeStore.accent === acc.key" :size="12" class="text-white"><Check /></el-icon>
                    </div>
                    <span class="accent-label">{{ acc.label }}</span>
                  </button>
                </div>
              </section>

              <!-- Language -->
              <section>
                <div class="section-heading">
                  <el-icon :size="12"><ChatLineRound /></el-icon>
                  {{ t('settings.language') }}
                </div>
                <div class="grid grid-cols-2 gap-2.5">
                  <button
                    v-for="opt in langOptions"
                    :key="opt.value"
                    class="lang-btn"
                    :class="{ active: themeStore.lang === opt.value }"
                    @click="themeStore.setLang(opt.value)"
                  >
                    <span class="lang-flag">{{ opt.flag }}</span>
                    <div class="lang-info">
                      <span class="lang-name">{{ opt.name }}</span>
                      <span class="lang-native">{{ opt.native }}</span>
                    </div>
                    <div v-if="themeStore.lang === opt.value" class="lang-check">
                      <el-icon :size="10" class="text-white"><Check /></el-icon>
                    </div>
                  </button>
                </div>
              </section>

            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useThemeStore, ACCENTS } from '@/stores/theme'
import type { LangKey } from '@/stores/theme'
import { Setting, Close, Check, Brush, ChatLineRound } from '@element-plus/icons-vue'

defineProps<{ visible: boolean }>()
const emit = defineEmits<{ (e: 'update:visible', v: boolean): void }>()

const themeStore = useThemeStore()
const { t } = useI18n()

function close() {
  emit('update:visible', false)
}

const langOptions = computed<{ value: LangKey; name: string; native: string; flag: string }[]>(() => [
  { value: 'zh', name: t('settings.langChinese'), native: '简体中文', flag: '🇨🇳' },
  { value: 'en', name: t('settings.langEnglish'), native: 'English', flag: '🇺🇸' },
])
</script>

<style scoped>
.overlay-fade-enter-active,
.overlay-fade-leave-active { transition: opacity 0.2s ease; }
.overlay-fade-enter-from,
.overlay-fade-leave-to { opacity: 0; }

.dialog-pop-enter-active { transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.2s ease; }
.dialog-pop-leave-active { transition: transform 0.15s ease, opacity 0.15s ease; }
.dialog-pop-enter-from { transform: scale(0.94) translateY(8px); opacity: 0; }
.dialog-pop-leave-to   { transform: scale(0.96) translateY(4px); opacity: 0; }

/* ── Accent color buttons ── */
.accent-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  padding: 8px 4px;
  border-radius: 10px;
  border: 1.5px solid transparent;
  background: transparent;
  cursor: pointer;
  transition: all 0.15s ease;
}
.accent-btn:hover {
  background: var(--color-surface-container);
}
.accent-btn.active {
  border-color: var(--color-brand);
  background: color-mix(in srgb, var(--color-brand) 8%, transparent);
}
.accent-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(0,0,0,0.15);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.accent-btn:hover .accent-dot {
  transform: scale(1.1);
  box-shadow: 0 3px 10px rgba(0,0,0,0.2);
}
.accent-btn.active .accent-dot {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-brand) 30%, transparent);
}
.accent-label {
  font-size: 10px;
  color: var(--color-on-surface-variant);
  font-weight: 500;
}
.accent-btn.active .accent-label {
  color: var(--color-brand);
}

/* ── Language buttons ── */
.lang-btn {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1.5px solid var(--color-outline-variant);
  background: var(--color-surface-container-low);
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: left;
}
.lang-btn:hover {
  border-color: var(--color-outline);
  background: var(--color-surface-container);
}
.lang-btn.active {
  border-color: var(--color-brand);
  background: color-mix(in srgb, var(--color-brand) 8%, transparent);
}
.lang-flag {
  font-size: 22px;
  line-height: 1;
  flex-shrink: 0;
}
.lang-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  flex: 1;
  min-width: 0;
}
.lang-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-on-surface);
}
.lang-native {
  font-size: 11px;
  color: var(--color-on-surface-variant);
}
.lang-check {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
</style>
