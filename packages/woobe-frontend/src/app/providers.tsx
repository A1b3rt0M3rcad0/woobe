import { type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/features/auth/AuthProvider'
import { WorkspaceProvider } from '@/features/workspace/WorkspaceProvider'
import { ThemeProvider, useTheme } from '@/features/appearance/ThemeProvider'
import { Toaster } from 'sonner'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
})

function ThemedProviders({ children }: { children: ReactNode }) {
  const { resolvedTheme } = useTheme()
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <WorkspaceProvider>
          {children}
          <Toaster
            position="bottom-right"
            theme={resolvedTheme}
            toastOptions={{
              style: {
                background: 'rgb(var(--woobe-surface))',
                border: '1px solid rgb(var(--woobe-border))',
                color: 'rgb(var(--woobe-ink))',
              },
            }}
          />
        </WorkspaceProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export function AppProviders({ children }: { children: ReactNode }) {
  return <ThemeProvider><ThemedProviders>{children}</ThemedProviders></ThemeProvider>
}
