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
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { orgProjectPath } from '@/lib/constants/routes'
import { Button } from '@/components/ui/Button'
import { SidebarUserCard } from './SidebarUserCard'

interface NavItem {
  label: string
  icon: LucideIcon
  href: string | ((orgId: string, projId: string) => string)
  end?: boolean
}

const buildNavItems: NavItem[] = [
  { label: 'Overview', icon: LayoutDashboard, href: (orgId: string, projId: string) => `/organizations/${orgId}/projects/${projId}`, end: true },
  { label: 'Agents', icon: Bot, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'agents') },
  { label: 'Knowledge', icon: BookOpen, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'knowledge') },
  { label: 'Tools', icon: Wrench, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'tools') },
]

const operateNavItems: NavItem[] = [
  { label: 'API Keys', icon: Key, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'api-keys') },
  { label: 'Usage', icon: BarChart3, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'usage') },
  { label: 'Traces', icon: Activity, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'traces') },
]

const accountNavItems: NavItem[] = [
  { label: 'Billing', icon: CreditCard, href: '/billing' },
  { label: 'Settings', icon: Settings, href: '/settings' },
]

function SidebarSectionTitle({ children }: { children: string }) {
  return (
    <p className="px-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted/80">
      {children}
    </p>
  )
}

function SidebarNavLink({ item, href }: { item: NavItem; href: string }) {
  const Icon = item.icon

  return (
    <NavLink
      to={href}
      end={item.end}
      className={({ isActive }) =>
        cn(
          'group flex items-center gap-3 rounded-xl border px-3 py-2 text-sm font-medium transition-[border-color,background-color,color,box-shadow]',
          isActive
            ? 'border-primary/35 bg-primary/10 text-primary-light shadow-[0_0_0_1px_rgba(59,130,246,0.12),0_10px_30px_rgba(37,99,235,0.06)]'
            : 'border-transparent text-muted hover:border-primary/20 hover:bg-background/70 hover:text-white',
        )
      }
    >
      <Icon className="h-4 w-4 shrink-0 transition-colors" />
      <span className="truncate">{item.label}</span>
    </NavLink>
  )
}

function ProjectNavGroup({ title, items, orgId, projId }: { title: string; items: NavItem[]; orgId: string; projId: string }) {
  return (
    <section className="space-y-2">
      <SidebarSectionTitle>{title}</SidebarSectionTitle>
      <div className="space-y-1">
        {items.map((item) => {
          const href = typeof item.href === 'function' ? item.href(orgId, projId) : item.href
          return <SidebarNavLink key={item.label} item={item} href={href} />
        })}
      </div>
    </section>
  )
}

function AccountNavGroup() {
  return (
    <section className="space-y-2 border-t border-border p-3">
      <SidebarSectionTitle>Account</SidebarSectionTitle>
      <div className="space-y-1">
        {accountNavItems.map((item) => (
          <SidebarNavLink key={item.label} item={item} href={item.href as string} />
        ))}
      </div>
    </section>
  )
}

function ProjectContextCard({ projectName, organizationName }: { projectName?: string; organizationName?: string }) {
  return (
    <div className="rounded-xl border border-border/80 bg-background/45 p-3">
      <p className="truncate text-sm font-semibold text-white">{projectName || 'Project workspace'}</p>
      <p className="mt-1 truncate text-xs text-muted">{organizationName || 'Project workspace'}</p>
    </div>
  )
}

function NoOrganizationState() {
  return (
    <div className="rounded-xl border border-border/80 bg-background/45 p-4 text-center">
      <p className="text-sm font-semibold text-white">Organization required</p>
      <p className="mt-1 text-xs leading-5 text-muted">Select an organization before opening a project workspace.</p>
    </div>
  )
}

function NoProjectState({ orgId }: { orgId: string }) {
  const navigate = useNavigate()
  return (
    <div className="rounded-xl border border-border/80 bg-background/45 p-4">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-surface text-primary-light">
        <FolderKanban className="h-4 w-4" />
      </div>
      <p className="mt-4 text-sm font-semibold text-white">Project required</p>
      <p className="mt-1 text-xs leading-5 text-muted">Select a project to access agents, knowledge, tools and runtime operations.</p>
      <Button
        size="sm"
        className="mt-4 w-full"
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
    <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-surface">
      <div className="border-b border-border p-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Play className="h-4 w-4 text-white" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-white">ProjectRAI</p>
            <p className="truncate text-xs text-muted">Control plane</p>
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <nav className="space-y-5 p-3">
          {!orgId ? (
            <NoOrganizationState />
          ) : !projId ? (
            <NoProjectState orgId={orgId} />
          ) : (
            <>
              <section className="space-y-2">
                <SidebarSectionTitle>Project</SidebarSectionTitle>
                <ProjectContextCard projectName={currentProject?.name} organizationName={currentOrganization?.name} />
              </section>

              <ProjectNavGroup title="Build" items={buildNavItems} orgId={orgId} projId={projId} />
              <ProjectNavGroup title="Operate" items={operateNavItems} orgId={orgId} projId={projId} />
            </>
          )}
        </nav>
      </ScrollArea>

      <AccountNavGroup />
      <SidebarUserCard />
    </aside>
  )
}
