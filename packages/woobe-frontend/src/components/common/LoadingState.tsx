import {
  LoadingState as WoobeLoadingState,
  type LoadingLayout,
  type LoadingStateProps,
  type LoadingVariant,
} from '@woobe/ui'

function getImplicitContext(message: string): { variant: LoadingVariant; layout: LoadingLayout } {
  const path = typeof window !== 'undefined' ? window.location.pathname : ''
  const normalized = message.toLowerCase()
  if (normalized.includes('authentication')) return { variant: 'fullscreen', layout: 'auth' }
  if (path === '/workspaces' || /^\/workspaces\/[^/]+\/projects$/.test(path)) return { variant: 'workspace', layout: 'cards' }
  if (path.includes('/usage')) return { variant: 'page', layout: 'metrics' }
  if (path.includes('/traces')) return { variant: 'page', layout: 'list' }
  return { variant: 'page', layout: 'cards' }
}

export function LoadingState({ message = 'Loading...', variant, layout, ...props }: LoadingStateProps) {
  const implicit = getImplicitContext(message)
  return (
    <WoobeLoadingState
      {...props}
      message={message}
      variant={variant ?? implicit.variant}
      layout={layout ?? implicit.layout}
    />
  )
}

export type { LoadingLayout, LoadingStateProps, LoadingVariant }
