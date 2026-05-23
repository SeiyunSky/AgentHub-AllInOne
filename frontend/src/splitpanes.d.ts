declare module 'splitpanes' {
  import { DefineComponent, Plugin } from 'vue'

  export interface PaneProps {
    size?: number
    minSize?: number
    maxSize?: number
  }

  export const Splitpanes: DefineComponent<{
    horizontal?: boolean
    pushOtherPanes?: boolean
    dblClickMaxMin?: boolean
    firstSplitter?: boolean
    class?: string
    style?: string | Record<string, string>
  }, {
    resized: (panes: PaneProps[]) => void
    paneAdd: (panes: PaneProps[]) => void
    paneRemove: (panes: PaneProps[]) => void
    splitpaneAdd: (panes: PaneProps[]) => void
    splitpaneRemove: (panes: PaneProps[]) => void
  }>

  export const Pane: DefineComponent<PaneProps>

  export const SplitpanesPlugin: Plugin
}