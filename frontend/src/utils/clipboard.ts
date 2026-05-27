/**
 * Copy text to clipboard with fallback for older browsers
 */
export async function copyToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
}

/**
 * Global handler for inline onclick in markdown-rendered code blocks
 * Called via window.__copyCode(buttonElement, codeId)
 */
;(window as any).__copyCode = async (btn: HTMLButtonElement, codeId: string) => {
  const el = document.getElementById(codeId)
  if (!el) return
  await copyToClipboard(el.textContent || '')
  btn.textContent = 'Copied!'
  setTimeout(() => { btn.textContent = 'Copy' }, 1500)
}