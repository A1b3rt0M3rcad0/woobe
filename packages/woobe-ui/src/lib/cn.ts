import { extendTailwindMerge } from 'tailwind-merge'
import { woobeFontSizes } from '../tokens/typography'

type ClassNameValue = string | false | null | undefined

// Unregistered text-* tokens are classified as colors. Register the same names
// used by the CSS preset so foreground utilities cannot erase semantic sizes.
export const mergeWoobeClasses = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [{ text: Object.keys(woobeFontSizes) }],
    },
  },
})

export function cn(...values: ClassNameValue[]) {
  return mergeWoobeClasses(values.filter(Boolean).join(' '))
}
