import { extendTailwindMerge } from 'tailwind-merge'
import { woobeFontSizes } from '../tokens/typography'

type ClassNameValue = string | false | null | undefined

// Unregistered text-* tokens are classified as colors. Register the same names
// used by the CSS preset so foreground utilities cannot erase semantic sizes.
export const mergeWoobeClasses = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [{ text: Object.keys(woobeFontSizes) }],
      'max-w': [{ 'max-w': ['resource', 'resource-wide', 'form-narrow', 'dialog-compact', 'dialog', 'dialog-wide', 'dialog-content', 'inspector', 'inspector-workspace', 'inspector-expanded', 'playground-agent-name', 'playground-agent-meta', 'conversation', 'conversation-compact'] }],
      'max-h': [{ 'max-h': ['dialog', 'sidebar-context', 'popover', 'trace-list', 'code-editor', 'multiline'] }],
      'rounded': [{ rounded: ['technical', 'control', 'container'] }],
    },
  },
})

export function cn(...values: ClassNameValue[]) {
  return mergeWoobeClasses(values.filter(Boolean).join(' '))
}
