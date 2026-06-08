import { createI18n } from 'vue-i18n'
import zhCN from '../locales/zh-CN'
import en from '../locales/en'

export type LangKey = 'zh' | 'en'

const LANG_KEY = 'agenthub-lang'

function getInitialLang(): LangKey {
  const stored = localStorage.getItem(LANG_KEY) as LangKey | null
  if (stored === 'zh' || stored === 'en') return stored
  return navigator.language.startsWith('zh') ? 'zh' : 'en'
}

export const i18n = createI18n({
  legacy: false,
  locale: getInitialLang(),
  fallbackLocale: 'en',
  messages: {
    zh: zhCN,
    en,
  },
})

export function applyLang(lang: LangKey) {
  i18n.global.locale.value = lang
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en'
}
