import MarkdownIt from 'markdown-it'
import { createHighlighter, type Highlighter } from 'shiki'
import DOMPurify from 'dompurify'

let highlighterPromise: Promise<Highlighter> | null = null
let cachedHighlighter: Highlighter | null = null

async function getHighlighter() {
  if (cachedHighlighter) return cachedHighlighter
  if (!highlighterPromise) {
    highlighterPromise = createHighlighter({
      themes: ['github-light'],
      langs: [
        'javascript', 'typescript', 'python', 'go', 'rust', 'java',
        'bash', 'shell', 'sql', 'json', 'yaml', 'toml',
        'html', 'css', 'vue', 'jsx', 'tsx', 'markdown',
        'c', 'cpp', 'diff', 'dockerfile', 'xml',
      ],
    }).then((h) => {
      cachedHighlighter = h
      return h
    })
  }
  return highlighterPromise
}

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
})

const fenceOriginal = md.renderer.rules.fence!

md.renderer.rules.fence = (tokens, idx, options, _env, self) => {
  const token = tokens[idx]
  const code = token.content.trim()
  const lang = (token.info || '').trim().split(/\s+/)[0] || 'text'
  const codeId = `code-${idx}-${Date.now()}`
  const wrapperId = `wrap-${idx}-${Date.now()}`

  const header = `<div class="shiki-header" data-action="toggle" data-target="${wrapperId}"><span class="shiki-toggle">▼</span><span class="shiki-lang">${lang}</span><button class="shiki-copy-btn" data-action="copy" data-target="${codeId}">Copy</button></div>`

  try {
    const hl = cachedHighlighter
    if (hl && lang !== 'text') {
      const loadedLangs = hl.getLoadedLanguages()
      const resolvedLang = loadedLangs.includes(lang) ? lang : 'text'
      const html = hl.codeToHtml(code, {
        lang: resolvedLang,
        themes: { light: 'github-light' },
      })
      return `<div id="${wrapperId}" class="shiki-wrapper">${header}<div id="${codeId}" class="shiki-code">${html}</div></div>`
    }
  } catch {}

  const fallback = fenceOriginal(tokens, idx, options, _env, self)
  return `<div id="${wrapperId}" class="shiki-wrapper">${header}<div id="${codeId}" class="shiki-code">${fallback}</div></div>`
}

export async function initHighlighter() {
  await getHighlighter()
}

export function renderMarkdown(text: string): string {
  const raw = md.render(text)
  return DOMPurify.sanitize(raw, {
    ADD_ATTR: ['id', 'data-action', 'data-target'],
  })
}

export function highlightCode(code: string, lang: string): string {
  const hl = cachedHighlighter
  if (!hl) return escapeHtml(code)

  try {
    const loadedLangs = hl.getLoadedLanguages()
    const resolvedLang = loadedLangs.includes(lang) ? lang : 'text'
    return hl.codeToHtml(code, {
      lang: resolvedLang,
      themes: { light: 'github-light' },
    })
  } catch {
    return escapeHtml(code)
  }
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
