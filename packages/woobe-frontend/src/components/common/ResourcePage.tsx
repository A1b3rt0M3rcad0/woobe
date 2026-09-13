import { ResourcePage as WoobeResourcePage } from '@woobe/ui'
import type { ResourcePageProps as WoobeResourcePageProps } from '@woobe/ui'

export type ResourcePageProps = Omit<WoobeResourcePageProps, 'eyebrow'>

export function ResourcePage(props: ResourcePageProps) {
  return <WoobeResourcePage {...props} eyebrow="Project resource" />
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
