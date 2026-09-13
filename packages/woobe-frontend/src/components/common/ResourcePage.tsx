import { ResourcePage as WoobeResourcePage } from '@woobe/ui'
import type { ResourcePageProps as WoobeResourcePageProps } from '@woobe/ui'

export type ResourcePageProps = Omit<WoobeResourcePageProps, 'eyebrow' | 'variant'>

export function ResourcePage({ className, ...props }: ResourcePageProps) {
  return <WoobeResourcePage {...props} variant="canvas" className={`${className ?? ''} !max-w-none`} />
}

export {
  ResourceEmptyState,
  ResourcePageHeader,
  ResourceSearch,
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@woobe/ui'
export type { ResourceTab } from '@woobe/ui'
