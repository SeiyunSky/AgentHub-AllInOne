import claudecodeIcon from '@/assets/icons/claudecode-color.svg'
import codexIcon from '@/assets/icons/codex-color.svg'
import opencodeIcon from '@/assets/icons/opencode.svg'
import magicIcon from '@/assets/icons/magic.svg'

const agentTypeIconMap: Record<string, string> = {
  claude: claudecodeIcon,
  claudecode: claudecodeIcon,
  anthropic_sdk: claudecodeIcon,
  codex: codexIcon,
  opencode: opencodeIcon,
  custom: magicIcon,
}

export function getAgentTypeIcon(type: string): string {
  return agentTypeIconMap[type] || magicIcon
}
