import { useNavigate, NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Bot,
  BookOpen,
  Wrench,
  Key,
  BarChart3,
  Activity,
  CreditCard,
  Settings,
  Play,
  FolderKanban,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { orgProjectPath } from '@/lib/constants/routes'
import { Button } from '@/components/ui/Button'

interface NavItem {
  label: string
  icon: typeof LayoutDashboard
  href: string | ((orgId: string, projId: string) => string)
  end?: boolean
}

const projectNavItems: NavItem[] = [
  { label: 'Overview', icon: LayoutDashboard, href: (orgId: string, projId: string) => `/organizations/${orgId}/projects/${projId}`, end: true },
  { label: 'Agents', icon: Bot, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'agents') },
  { label: 'Knowledge', icon: BookOpen, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'knowledge') },
  { label: 'Tools', icon: Wrench, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'tools') },
  { label: 'API Keys', icon: Key, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'api-keys') },
  { label: 'Usage', icon: BarChart3, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'usage') },
  { label: 'Traces', icon: Activity, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'traces') },
]

const bottomItems: NavItem[] = [
  { label: 'Billing', icon: CreditCard, href: '/billing' },
  { label: 'Settings', icon: Settings, href: '/settings' },
]

function NoProjectState({ orgId }: { orgId: string }) {
  const navigate = useNavigate()
  return (
    <div className="px-3 py-6 text-center">
      <FolderKanban className="mx-auto h-8 w-8 text-muted mb-3" />
      <p className="text-sm font-medium text-white mb-1">No project selected</p>
      <p className="text-xs text-muted mb-4">
        Select a project to access agents, knowledge and API keys.
      </p>
      <Button
        size="sm"
        onClick={() => navigate(`/organizations/${orgId}/projects`)}
      >
        <FolderKanban className="mr-1.5 h-3.5 w-3.5" />
        Select project
      </Button>
    </div>
  )
}

export function Sidebar() {
  const { currentOrganization, currentProject } = useWorkspace()
  const orgId = currentOrganization?.id
  const projId = currentProject?.id

  return (
    <aside className="flex w-60 flex-col border-r border-border bg-surface">
      <div className="flex h-14 items-center gap-2 border-b border-border px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
          <Play className="h-4 w-4 text-white" />
        </div>
        <span className="font-semibold text-white">ProjectRAI</span>
      </div>

      <nav className="flex-1 overflow-y-auto p-3 space-y-1">
        {!orgId ? (
          <div className="px-3 py-6 text-center">
            <p className="text-sm text-muted">Select an organization first</p>
          </div>
        ) : !projId ? (
          <NoProjectState orgId={orgId} />
        ) : (
          <>
            <div className="pb-1">
              <p className="px-3 text-xs font-medium text-muted uppercase tracking-wider truncate">
                {currentProject?.name}
              </p>
            </div>

            {projectNavItems.map((item) => {
              const href = typeof item.href === 'function' ? item.href(orgId, projId) : item.href
              return (
                <NavLink
                  key={item.label}
                  to={href}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-primary/10 text-primary'
                        : 'text-muted hover:bg-accent hover:text-white',
                    )
                  }
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </NavLink>
              )
            })}
          </>
        )}
      </nav>

      <div className="border-t border-border p-3 space-y-1">
        {bottomItems.map((item) => (
          <NavLink
            key={item.label}
            to={item.href as string}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted hover:bg-accent hover:text-white',
              )
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </div>
    </aside>
  )
}
