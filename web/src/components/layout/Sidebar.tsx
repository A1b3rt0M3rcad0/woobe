import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Building2,
  FolderKanban,
  Bot,
  BookOpen,
  Wrench,
  Key,
  BarChart3,
  Activity,
  CreditCard,
  Settings,
  Play,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { orgProjectPath } from '@/lib/constants/routes'

interface NavItem {
  label: string
  icon: typeof LayoutDashboard
  href: string | ((orgId: string, projId: string) => string)
  requiresProject: boolean
  requiresOrganization: boolean
}

const topItems: NavItem[] = [
  { label: 'Overview', icon: LayoutDashboard, href: '/dashboard', requiresProject: false, requiresOrganization: false },
  { label: 'Organizations', icon: Building2, href: '/organizations', requiresProject: false, requiresOrganization: false },
  { label: 'Projects', icon: FolderKanban, href: (orgId: string) => `/organizations/${orgId}/projects`, requiresProject: false, requiresOrganization: true },
]

const projectItems: NavItem[] = [
  { label: 'Agents', icon: Bot, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'agents'), requiresProject: true, requiresOrganization: true },
  { label: 'Knowledge', icon: BookOpen, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'knowledge'), requiresProject: true, requiresOrganization: true },
  { label: 'Tools', icon: Wrench, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'tools'), requiresProject: true, requiresOrganization: true },
  { label: 'API Keys', icon: Key, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'api-keys'), requiresProject: true, requiresOrganization: true },
  { label: 'Usage', icon: BarChart3, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'usage'), requiresProject: true, requiresOrganization: true },
  { label: 'Traces', icon: Activity, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'traces'), requiresProject: true, requiresOrganization: true },
]

const bottomItems: NavItem[] = [
  { label: 'Billing', icon: CreditCard, href: '/billing', requiresProject: false, requiresOrganization: false },
  { label: 'Settings', icon: Settings, href: '/settings', requiresProject: false, requiresOrganization: false },
]

function resolveHref(item: NavItem, orgId: string | undefined, projId: string | undefined): string {
  if (typeof item.href === 'string') return item.href
  if (item.requiresProject && orgId && projId) return item.href(orgId, projId)
  if (item.requiresOrganization && orgId) return item.href(orgId, '')
  return '#'
}

export function Sidebar() {
  const { currentOrganization, currentProject } = useWorkspace()
  const location = useLocation()
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
        {topItems.map((item) => {
          if (item.requiresOrganization && !orgId) {
            return (
              <div
                key={item.label}
                className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted/50"
                title="Select an organization first"
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </div>
            )
          }
          const href = resolveHref(item, orgId, projId)
          return (
            <NavLink
              key={item.label}
              to={href}
              end={item.label === 'Overview' || item.label === 'Organizations'}
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

        {projId && orgId && (
          <div className="pt-3 pb-1">
            <p className="px-3 text-xs font-medium text-muted uppercase tracking-wider">
              {currentProject?.name}
            </p>
          </div>
        )}

        {projectItems.map((item) => {
          if (!orgId || !projId) {
            return (
              <div
                key={item.label}
                className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted/50"
                title={!orgId ? 'Select an organization first' : 'Select a project first'}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </div>
            )
          }
          const href = resolveHref(item, orgId, projId)
          return (
            <NavLink
              key={item.label}
              to={href}
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
