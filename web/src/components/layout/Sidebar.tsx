import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Workflow,
  Bot,
  BookOpen,
  Wrench,
  Boxes,
  Cable,
  Key,
  BarChart3,
  Activity,
  CreditCard,
  Settings,
  Play,
  FolderKanban,
  Building2,
  ChevronDown,
  List,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { orgProjectPath } from '@/lib/constants/routes'
import type { OrgShape, ProjectShape } from '@/features/workspace/types'
import { SidebarUserCard } from './SidebarUserCard'

interface NavItem {
  label: string
  icon: LucideIcon
  href: string | ((orgId: string, projId: string) => string)
  end?: boolean
}

const buildNavItems: NavItem[] = [
  { label: 'Overview', icon: LayoutDashboard, href: (orgId: string, projId: string) => `/organizations/${orgId}/projects/${projId}`, end: true },
  { label: 'Network', icon: Workflow, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'network') },
  { label: 'Agents', icon: Bot, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'agents') },
  { label: 'Knowledge', icon: BookOpen, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'knowledge') },
  { label: 'Tools', icon: Wrench, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'tools') },
  { label: 'Models', icon: Boxes, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'models') },
  { label: 'Credentials', icon: Cable, href: (orgId: string, projId: string) => orgProjectPath(orgId, projId, 'credentials') },
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

function ContextMenuItem({ icon: Icon, title, description, active, onClick }: { icon: LucideIcon; title: string; description?: string; active?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex w-full items-start gap-2 rounded-lg border px-2.5 py-2 text-left transition-[border-color,background-color,color,transform] duration-150 ease-out active:scale-[0.99]',
        active
          ? 'border-primary/30 bg-primary/10 text-white'
          : 'border-transparent text-muted hover:border-primary/20 hover:bg-background/70 hover:text-white',
      )}
    >
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-xs font-medium">{title}</span>
        {description && <span className="mt-0.5 block truncate text-[11px] text-muted">{description}</span>}
      </span>
    </button>
  )
}

function ProjectContextCard({
  currentOrganization,
  currentProject,
  organizations,
  projects,
  selectOrganization,
  selectProject,
}: {
  currentOrganization: OrgShape
  currentProject: ProjectShape
  organizations: OrgShape[]
  projects: ProjectShape[]
  selectOrganization: (org: OrgShape) => void
  selectProject: (project: ProjectShape) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    if (open) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  const handleProjectSelect = (project: ProjectShape) => {
    selectProject(project)
    navigate(`/organizations/${currentOrganization.id}/projects/${project.id}`)
    setOpen(false)
  }

  const handleOrganizationSelect = (organization: OrgShape) => {
    selectOrganization(organization)
    navigate(`/organizations/${organization.id}/projects`)
    setOpen(false)
  }

  const navigateAndClose = (href: string) => {
    navigate(href)
    setOpen(false)
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className={cn(
          'group w-full rounded-xl border bg-background/45 p-3 text-left transition-[border-color,background-color,box-shadow,transform] duration-200 ease-out active:scale-[0.99]',
          open
            ? 'border-primary/35 bg-primary/10 shadow-[0_0_0_1px_rgba(59,130,246,0.12),0_10px_30px_rgba(37,99,235,0.06)]'
            : 'border-border/80 hover:border-primary/25 hover:bg-background/70',
        )}
      >
        <span className="flex items-start justify-between gap-2">
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold text-white">{currentProject.name}</span>
            <span className="mt-1 block truncate text-xs text-muted">{currentOrganization.name}</span>
          </span>
          <ChevronDown className={cn('mt-0.5 h-3.5 w-3.5 shrink-0 text-muted transition-[color,transform] duration-200 ease-out', open && 'rotate-180 text-primary-light')} />
        </span>
      </button>

      <div
        aria-hidden={!open}
        className={cn(
          'absolute left-0 right-0 top-full z-40 mt-2 origin-top rounded-xl border border-border bg-surface p-2 shadow-2xl shadow-black/30 transition-[opacity,transform,filter] duration-200 ease-out will-change-transform',
          open
            ? 'pointer-events-auto translate-y-0 scale-100 opacity-100 blur-0'
            : 'pointer-events-none -translate-y-1 scale-[0.98] opacity-0 blur-[1px]',
        )}
      >
        <div className="space-y-2">
          <div>
            <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted/80">Switch project</p>
            <div className="max-h-44 space-y-1 overflow-y-auto pr-1 scrollbar-thin">
              {projects.length === 0 ? (
                <p className="px-2 py-2 text-xs text-muted">No projects available</p>
              ) : projects.map((project) => (
                <ContextMenuItem
                  key={project.id}
                  icon={FolderKanban}
                  title={project.name}
                  description="Project workspace"
                  active={project.id === currentProject.id}
                  onClick={() => handleProjectSelect(project)}
                />
              ))}
            </div>
          </div>

          <div className="border-t border-border pt-2">
            <ContextMenuItem
              icon={List}
              title="Manage projects"
              description="Select, create or review projects"
              onClick={() => navigateAndClose(`/organizations/${currentOrganization.id}/projects`)}
            />
            <ContextMenuItem
              icon={Settings}
              title="Project settings"
              description="Configure this project"
              onClick={() => navigateAndClose(`/organizations/${currentOrganization.id}/projects/${currentProject.id}/settings`)}
            />
          </div>

          <div className="border-t border-border pt-2">
            <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted/80">Organization</p>
            {organizations.map((organization) => (
              <ContextMenuItem
                key={organization.id}
                icon={Building2}
                title={organization.name}
                description="Organization workspace"
                active={organization.id === currentOrganization.id}
                onClick={() => handleOrganizationSelect(organization)}
              />
            ))}
            <ContextMenuItem
              icon={List}
              title="Manage organizations"
              description="Select, create or review organizations"
              onClick={() => navigateAndClose('/organizations')}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

function ProjectContextSkeleton() {
  return (
    <div className="space-y-4" aria-label="Loading workspace">
      <div className="animate-pulse rounded-xl border border-border/80 bg-background/45 p-3">
        <div className="h-3.5 w-28 rounded bg-border/80" />
        <div className="mt-2 h-3 w-20 rounded bg-border/50" />
      </div>
      <div className="space-y-2 px-2">
        <div className="h-2.5 w-12 animate-pulse rounded bg-border/50" />
        <div className="h-9 animate-pulse rounded-xl bg-background/55" />
        <div className="h-9 animate-pulse rounded-xl bg-background/55" />
        <div className="h-9 animate-pulse rounded-xl bg-background/55" />
      </div>
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

export function Sidebar() {
  const { pathname } = useLocation()
  const {
    organizations,
    currentOrganization,
    projects,
    currentProject,
    selectOrganization,
    selectProject,
    isLoadingOrganizations,
    isLoadingProjects,
  } = useWorkspace()
  const orgId = currentOrganization?.id
  const projId = currentProject?.id
  const isProjectRoute = /^\/organizations\/[^/]+\/projects\/[^/]+(?:\/|$)/.test(pathname)
  const isResolvingProjectContext = isProjectRoute && (
    isLoadingOrganizations
    || isLoadingProjects
    || !currentOrganization
    || !currentProject
  )

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-surface">
      <div className="border-b border-border p-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Play className="h-4 w-4 text-white" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-white">Woobe</p>
            <p className="truncate text-xs text-muted">Control plane</p>
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <nav className="space-y-5 p-3">
          {isResolvingProjectContext ? (
            <ProjectContextSkeleton />
          ) : !orgId || !currentOrganization ? (
            <NoOrganizationState />
          ) : projId && currentProject ? (
            <>
              <section className="space-y-2">
                <SidebarSectionTitle>Project</SidebarSectionTitle>
                <ProjectContextCard
                  currentOrganization={currentOrganization}
                  currentProject={currentProject}
                  organizations={organizations}
                  projects={projects}
                  selectOrganization={selectOrganization}
                  selectProject={selectProject}
                />
              </section>

              <ProjectNavGroup title="Build" items={buildNavItems} orgId={orgId} projId={projId} />
              <ProjectNavGroup title="Operate" items={operateNavItems} orgId={orgId} projId={projId} />
            </>
          ) : null}
        </nav>
      </ScrollArea>

      <AccountNavGroup />
      <SidebarUserCard />
    </aside>
  )
}
