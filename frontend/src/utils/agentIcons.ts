import claudecodeIcon from '@/assets/icons/claudecode-color.svg'
import codexIcon from '@/assets/icons/codex-color.svg'
import openaiIcon from '@/assets/icons/openai.svg'
import opencodeIcon from '@/assets/icons/opencode.svg'
import deepseekIcon from '@/assets/icons/deepseek-color.svg'
import geminiIcon from '@/assets/icons/gemini-color.svg'
import ollamaIcon from '@/assets/icons/ollama.svg'
import qwenIcon from '@/assets/icons/qwen-color.svg'
import magicIcon from '@/assets/icons/magic.svg'

/**
 * Maps agent type to local SVG icon URL (resolved by Vite).
 */
const agentTypeIconMap: Record<string, string> = {
  claude: claudecodeIcon,
  claudecode: claudecodeIcon,
  codex: codexIcon,
  opencode: opencodeIcon,
  openai: openaiIcon,
  deepseek: deepseekIcon,
  gemini: geminiIcon,
  ollama: ollamaIcon,
  qwen: qwenIcon,
  custom: magicIcon,
}

/**
 * Get the local icon URL for an agent type.
 */
export function getAgentTypeIcon(type: string): string {
  return agentTypeIconMap[type] || openaiIcon
}
