import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type AccentKey = 'violet' | 'blue' | 'emerald' | 'rose' | 'amber' | 'cyan'
export type LangKey = 'zh' | 'en'

const ACCENT_KEY = 'agenthub-accent'
const LANG_KEY   = 'agenthub-lang'
const TOKENS_KEY = 'agenthub-tokens'

export interface AccentPalette {
  key: AccentKey
  label: string
  color: string       // preview dot
  light: Record<string, string>
  dark:  Record<string, string>
}

export const ACCENTS: AccentPalette[] = [
  {
    key: 'violet',
    label: 'Violet',
    color: '#6366f1',
    light: {
      '--color-brand':         '#6366f1',
      '--color-brand-dark':    '#4338ca',
      '--color-brand-light':   '#eef2ff',
      '--color-brand-subtle':  '#e0e7ff',
      '--color-outline':       '#a5b4fc',
      '--color-outline-variant': '#e0e7ff',
      '--color-surface':       '#f5f3ff',
      '--color-surface-container-low': '#f0ebff',
      '--color-surface-container': '#f5f3ff',
      '--color-surface-container-high': '#e4dcf9',
      '--color-surface-container-highest': '#d5c9f5',
      '--color-on-surface':    '#1e1b4b',
      '--color-rail-bg':       '#1a1040',
      '--color-rail-surface':  '#2d1b69',
      '--color-logo-gradient': 'linear-gradient(135deg, #e0d7ff 0%, #a78bfa 60%, #7c3aed 100%)',
      '--shadow-glow':         '0 0 24px rgba(99,102,241,0.25)',
    },
    dark: {
      '--color-brand':         '#818cf8',
      '--color-brand-dark':    '#6366f1',
      '--color-brand-light':   '#1e1b4b',
      '--color-brand-subtle':  '#312e81',
      '--color-outline':       '#3730a3',
      '--color-outline-variant': '#1e1b4b',
      '--color-surface':       '#0f0e17',
      '--color-surface-container-low': '#13111f',
      '--color-surface-container': '#1a1827',
      '--color-surface-container-high': '#231f35',
      '--color-surface-container-highest': '#2d2845',
      '--color-on-surface':    '#e2e0f0',
      '--color-rail-bg':       '#0d0a1e',
      '--color-rail-surface':  '#1a1040',
      '--color-logo-gradient': 'linear-gradient(135deg, #e0d7ff 0%, #a78bfa 60%, #7c3aed 100%)',
      '--shadow-glow':         '0 0 24px rgba(129,140,248,0.3)',
    },
  },
  {
    key: 'blue',
    label: 'Blue',
    color: '#3b82f6',
    light: {
      '--color-brand':         '#3b82f6',
      '--color-brand-dark':    '#1d4ed8',
      '--color-brand-light':   '#eff6ff',
      '--color-brand-subtle':  '#dbeafe',
      '--color-outline':       '#93c5fd',
      '--color-outline-variant': '#dbeafe',
      '--color-surface':       '#f0f7ff',
      '--color-surface-container-low': '#e8f0fe',
      '--color-surface-container': '#f0f7ff',
      '--color-surface-container-high': '#dce8fb',
      '--color-surface-container-highest': '#c7d9f7',
      '--color-on-surface':    '#1e3a5f',
      '--color-rail-bg':       '#0a1628',
      '--color-rail-surface':  '#102550',
      '--color-logo-gradient': 'linear-gradient(135deg, #bfdbfe 0%, #60a5fa 60%, #1d4ed8 100%)',
      '--shadow-glow':         '0 0 24px rgba(59,130,246,0.25)',
    },
    dark: {
      '--color-brand':         '#60a5fa',
      '--color-brand-dark':    '#3b82f6',
      '--color-brand-light':   '#1e3a5f',
      '--color-brand-subtle':  '#1e3a8a',
      '--color-outline':       '#1e40af',
      '--color-outline-variant': '#1e3a5f',
      '--color-surface':       '#0d1117',
      '--color-surface-container-low': '#111827',
      '--color-surface-container': '#172030',
      '--color-surface-container-high': '#1f2d42',
      '--color-surface-container-highest': '#283b55',
      '--color-on-surface':    '#dde8f8',
      '--color-rail-bg':       '#060e1a',
      '--color-rail-surface':  '#0a1e3a',
      '--color-logo-gradient': 'linear-gradient(135deg, #bfdbfe 0%, #60a5fa 60%, #1d4ed8 100%)',
      '--shadow-glow':         '0 0 24px rgba(96,165,250,0.3)',
    },
  },
  {
    key: 'emerald',
    label: 'Emerald',
    color: '#10b981',
    light: {
      '--color-brand':         '#10b981',
      '--color-brand-dark':    '#047857',
      '--color-brand-light':   '#ecfdf5',
      '--color-brand-subtle':  '#d1fae5',
      '--color-outline':       '#6ee7b7',
      '--color-outline-variant': '#d1fae5',
      '--color-surface':       '#f0fdf8',
      '--color-surface-container-low': '#e6faf3',
      '--color-surface-container': '#f0fdf8',
      '--color-surface-container-high': '#d8f5ec',
      '--color-surface-container-highest': '#b8ebd8',
      '--color-on-surface':    '#064e3b',
      '--color-rail-bg':       '#051a10',
      '--color-rail-surface':  '#0a2d1c',
      '--color-logo-gradient': 'linear-gradient(135deg, #a7f3d0 0%, #34d399 60%, #047857 100%)',
      '--shadow-glow':         '0 0 24px rgba(16,185,129,0.25)',
    },
    dark: {
      '--color-brand':         '#34d399',
      '--color-brand-dark':    '#10b981',
      '--color-brand-light':   '#064e3b',
      '--color-brand-subtle':  '#065f46',
      '--color-outline':       '#065f46',
      '--color-outline-variant': '#064e3b',
      '--color-surface':       '#0a1410',
      '--color-surface-container-low': '#0f1c18',
      '--color-surface-container': '#152620',
      '--color-surface-container-high': '#1d342b',
      '--color-surface-container-highest': '#264237',
      '--color-on-surface':    '#d1fae5',
      '--color-rail-bg':       '#03100a',
      '--color-rail-surface':  '#071c12',
      '--color-logo-gradient': 'linear-gradient(135deg, #a7f3d0 0%, #34d399 60%, #047857 100%)',
      '--shadow-glow':         '0 0 24px rgba(52,211,153,0.3)',
    },
  },
  {
    key: 'rose',
    label: 'Rose',
    color: '#f43f5e',
    light: {
      '--color-brand':         '#f43f5e',
      '--color-brand-dark':    '#be123c',
      '--color-brand-light':   '#fff1f2',
      '--color-brand-subtle':  '#ffe4e6',
      '--color-outline':       '#fda4af',
      '--color-outline-variant': '#ffe4e6',
      '--color-surface':       '#fff5f6',
      '--color-surface-container-low': '#ffe8ea',
      '--color-surface-container': '#fff5f6',
      '--color-surface-container-high': '#ffd6da',
      '--color-surface-container-highest': '#ffc0c7',
      '--color-on-surface':    '#4c0519',
      '--color-rail-bg':       '#1a080d',
      '--color-rail-surface':  '#2e1018',
      '--color-logo-gradient': 'linear-gradient(135deg, #fecdd3 0%, #fb7185 60%, #be123c 100%)',
      '--shadow-glow':         '0 0 24px rgba(244,63,94,0.25)',
    },
    dark: {
      '--color-brand':         '#fb7185',
      '--color-brand-dark':    '#f43f5e',
      '--color-brand-light':   '#4c0519',
      '--color-brand-subtle':  '#881337',
      '--color-outline':       '#9f1239',
      '--color-outline-variant': '#4c0519',
      '--color-surface':       '#180a0d',
      '--color-surface-container-low': '#200f13',
      '--color-surface-container': '#2a141a',
      '--color-surface-container-high': '#371c23',
      '--color-surface-container-highest': '#44242d',
      '--color-on-surface':    '#ffe4e6',
      '--color-rail-bg':       '#10060a',
      '--color-rail-surface':  '#1e0c12',
      '--color-logo-gradient': 'linear-gradient(135deg, #fecdd3 0%, #fb7185 60%, #be123c 100%)',
      '--shadow-glow':         '0 0 24px rgba(251,113,133,0.3)',
    },
  },
  {
    key: 'amber',
    label: 'Amber',
    color: '#f59e0b',
    light: {
      '--color-brand':         '#f59e0b',
      '--color-brand-dark':    '#b45309',
      '--color-brand-light':   '#fffbeb',
      '--color-brand-subtle':  '#fef3c7',
      '--color-outline':       '#fcd34d',
      '--color-outline-variant': '#fef3c7',
      '--color-surface':       '#fffdf0',
      '--color-surface-container-low': '#fef9e0',
      '--color-surface-container': '#fffdf0',
      '--color-surface-container-high': '#fdf0c4',
      '--color-surface-container-highest': '#fae3a0',
      '--color-on-surface':    '#451a03',
      '--color-rail-bg':       '#1a1005',
      '--color-rail-surface':  '#2d1e0a',
      '--color-logo-gradient': 'linear-gradient(135deg, #fef3c7 0%, #fbbf24 60%, #b45309 100%)',
      '--shadow-glow':         '0 0 24px rgba(245,158,11,0.25)',
    },
    dark: {
      '--color-brand':         '#fbbf24',
      '--color-brand-dark':    '#f59e0b',
      '--color-brand-light':   '#451a03',
      '--color-brand-subtle':  '#78350f',
      '--color-outline':       '#92400e',
      '--color-outline-variant': '#451a03',
      '--color-surface':       '#16120a',
      '--color-surface-container-low': '#1e190e',
      '--color-surface-container': '#252014',
      '--color-surface-container-high': '#2e291b',
      '--color-surface-container-highest': '#383222',
      '--color-on-surface':    '#fef3c7',
      '--color-rail-bg':       '#100b03',
      '--color-rail-surface':  '#1e1505',
      '--color-logo-gradient': 'linear-gradient(135deg, #fef3c7 0%, #fbbf24 60%, #b45309 100%)',
      '--shadow-glow':         '0 0 24px rgba(251,191,36,0.3)',
    },
  },
  {
    key: 'cyan',
    label: 'Cyan',
    color: '#06b6d4',
    light: {
      '--color-brand':         '#06b6d4',
      '--color-brand-dark':    '#0e7490',
      '--color-brand-light':   '#ecfeff',
      '--color-brand-subtle':  '#cffafe',
      '--color-outline':       '#67e8f9',
      '--color-outline-variant': '#cffafe',
      '--color-surface':       '#f0feff',
      '--color-surface-container-low': '#e0fafb',
      '--color-surface-container': '#f0feff',
      '--color-surface-container-high': '#c8f3f7',
      '--color-surface-container-highest': '#a5e9ef',
      '--color-on-surface':    '#083344',
      '--color-rail-bg':       '#071520',
      '--color-rail-surface':  '#0c2535',
      '--color-logo-gradient': 'linear-gradient(135deg, #a5f3fc 0%, #22d3ee 60%, #0e7490 100%)',
      '--shadow-glow':         '0 0 24px rgba(6,182,212,0.25)',
    },
    dark: {
      '--color-brand':         '#22d3ee',
      '--color-brand-dark':    '#06b6d4',
      '--color-brand-light':   '#083344',
      '--color-brand-subtle':  '#164e63',
      '--color-outline':       '#155e75',
      '--color-outline-variant': '#083344',
      '--color-surface':       '#09131a',
      '--color-surface-container-low': '#0f1c24',
      '--color-surface-container': '#15252e',
      '--color-surface-container-high': '#1d3040',
      '--color-surface-container-highest': '#263d4e',
      '--color-on-surface':    '#cffafe',
      '--color-rail-bg':       '#04100a',
      '--color-rail-surface':  '#081a28',
      '--color-logo-gradient': 'linear-gradient(135deg, #a5f3fc 0%, #22d3ee 60%, #0e7490 100%)',
      '--shadow-glow':         '0 0 24px rgba(34,211,238,0.3)',
    },
  },
]

function getSystemDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function applyAccent(accentKey: AccentKey, isDark: boolean) {
  const palette = ACCENTS.find(a => a.key === accentKey) ?? ACCENTS[0]
  const tokens = isDark ? palette.dark : palette.light
  const root = document.documentElement
  for (const [prop, val] of Object.entries(tokens)) {
    root.style.setProperty(prop, val)
  }
  try { localStorage.setItem(TOKENS_KEY, JSON.stringify(tokens)) } catch {}
}

function applyTheme(accentKey: AccentKey) {
  const dark = getSystemDark()
  document.documentElement.classList.toggle('dark', dark)
  applyAccent(accentKey, dark)
}

export const useThemeStore = defineStore('theme', () => {
  const savedAccent = localStorage.getItem(ACCENT_KEY) as AccentKey | null
  const savedLang = localStorage.getItem(LANG_KEY) as LangKey | null
  const accent = ref<AccentKey>(savedAccent ?? 'violet')
  const lang   = ref<LangKey>(savedLang ?? 'zh')

  applyTheme(accent.value)

  watch(accent, (val) => {
    localStorage.setItem(ACCENT_KEY, val)
    applyAccent(val, getSystemDark())
  })

  watch(lang, (val) => {
    localStorage.setItem(LANG_KEY, val)
  })

  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  mediaQuery.addEventListener('change', () => applyTheme(accent.value))

  function setAccent(val: AccentKey) { accent.value = val }
  function setLang(val: LangKey)     { lang.value = val }

  return { accent, lang, setAccent, setLang }
})
