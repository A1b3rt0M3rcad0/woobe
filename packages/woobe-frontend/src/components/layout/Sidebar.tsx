import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Workflow,
  Bot,
  BookOpen,
  Wrench,
  Puzzle,
  Boxes,
  Cable,
  Key,
  BarChart3,
  Activity,
  Settings,
  FolderKanban,
  Building2,
  ChevronDown,
  List,
  MessageSquare,
  Orbit,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { WorkspaceSettingsDialog } from '@/features/workspaces/components/WorkspaceSettingsDialog'
import { ProjectSettingsDialog } from '@/features/projects/components/ProjectSettingsDialog'
import { workspaceProjectPath } from '@/lib/constants/routes'
import type { WorkspaceShape, ProjectShape } from '@/features/workspace/types'
import { SidebarUserCard } from './SidebarUserCard'

interface NavItem {
  label: string
  icon: LucideIcon
  href: string | ((workspaceId: string, projId: string) => string)
  end?: boolean
}

const buildNavItems: NavItem[] = [
  { label: 'Overview', icon: LayoutDashboard, href: (workspaceId: string, projId: string) => `/workspaces/${workspaceId}/projects/${projId}`, end: true },
  { label: 'Network', icon: Workflow, href: (workspaceId: string, projId: string) => workspaceProjectPath(workspaceId, projId, 'network') },
  { label: 'Agents', icon: Bot, href: (workspaceId: string, projId: string) => workspaceProjectPath(workspaceId, projId, 'agents') },
  { label: 'Knowledge', icon: BookOpen, href: (workspaceId: string, projId: string) => workspaceProjectPath(workspaceId, projId, 'knowledge') },
  { label: 'Tools', icon: Wrench, href: (workspaceId: string, projId: string) => workspaceProjectPath(workspaceId, projId, 'tools') },
  { label: 'Skills', icon: Puzzle, href: (workspaceId: string, projId: string) => workspaceProjectPath(workspaceId, projId, 'skills') },
  { label: 'Models', icon: Boxes, href: (workspaceId: string, projId: string) => workspaceProjectPath(workspaceId, projId, 'models') },
  { label: 'Credentials', icon: Cable, href: (workspaceId: string, projId: string) => workspaceProjectPath(workspaceId, projId, 'credentials') },
]

const operateNavItems: NavItem[] = [
  { label: 'ChatSurfaces', icon: MessageSquare, href: (workspaceId: string, projId: string) => workspaceProjectPath(workspaceId, projId, 'chat-surfaces') },
  { label: 'API Keys', icon: Key, href: (workspaceId: string, projId: string) => workspaceProjectPath(workspaceId, projId, 'api-keys') },
  { label: 'Usage', icon: BarChart3, href: (workspaceId: string, projId: string) => workspaceProjectPath(workspaceId, projId, 'usage') },
  { label: 'Traces', icon: Activity, href: (workspaceId: string, projId: string) => workspaceProjectPath(workspaceId, projId, 'traces') },
]

function SidebarSectionTitle({ children }: { children: string }) {
  return (
    <p className="mb-ui-sm px-ui-sm font-mono text-system-label font-bold uppercase tracking-[0.15em] text-muted-foreground">
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
          'group flex h-control-nav items-center gap-ui-sm rounded-technical border px-ui-sm font-mono text-system-control transition-colors',
          isActive
            ? 'border-primary/45 bg-primary/[0.12] text-slate-50'
            : 'border-transparent text-slate-300 hover:border-border hover:bg-accent/45 hover:text-slate-50',
        )
      }
    >
      <Icon className="h-icon w-icon shrink-0 text-muted-foreground transition-colors group-hover:text-slate-200" />
      <span className="truncate">{item.label}</span>
    </NavLink>
  )
}

function ProjectNavGroup({ title, items, workspaceId, projId }: { title: string; items: NavItem[]; workspaceId: string; projId: string }) {
  return (
    <section>
      <SidebarSectionTitle>{title}</SidebarSectionTitle>
      <div className="grid gap-ui-hairline">
        {items.map((item) => {
          const href = typeof item.href === 'function' ? item.href(workspaceId, projId) : item.href
          return <SidebarNavLink key={item.label} item={item} href={href} />
        })}
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
        'flex w-full items-start gap-ui-sm rounded-control border px-ui-sm py-ui-sm text-left font-mono transition-colors',
        active
          ? 'border-primary/35 bg-primary/[0.1] text-slate-50'
          : 'border-transparent text-slate-300 hover:border-border hover:bg-control hover:text-slate-50',
      )}
    >
      <Icon className="mt-ui-hairline h-icon w-icon shrink-0 text-muted-foreground" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-system-control font-medium">{title}</span>
        {description && <span className="mt-ui-xs block truncate text-system-meta text-muted-foreground">{description}</span>}
      </span>
    </button>
  )
}

function ProjectContextCard({
  currentWorkspace,
  currentProject,
  workspaces,
  projects,
  selectWorkspace,
  selectProject,
}: {
  currentWorkspace: WorkspaceShape
  currentProject: ProjectShape
  workspaces: WorkspaceShape[]
  projects: ProjectShape[]
  selectWorkspace: (workspace: WorkspaceShape) => void
  selectProject: (project: ProjectShape) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  const handleProjectSelect = (project: ProjectShape) => {
    selectProject(project)
    navigate(`/workspaces/${currentWorkspace.id}/projects/${project.id}`)
    setOpen(false)
  }

  const handleWorkspaceSelect = (workspace: WorkspaceShape) => {
    selectWorkspace(workspace)
    navigate(`/workspaces/${workspace.id}/projects`)
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
          'group w-full rounded-container border bg-control/45 px-ui-md py-ui-sm text-left transition-colors',
          open ? 'border-primary/40 bg-primary/[0.08]' : 'border-border hover:border-slate-600 hover:bg-control',
        )}
      >
        <span className="flex items-center justify-between gap-ui-sm">
          <span className="min-w-0 flex-1">
            <span className="block truncate font-mono text-product-small font-bold text-slate-50">{currentProject.name}</span>
            <span className="mt-ui-xs block truncate font-mono text-system-meta text-muted-foreground">{currentWorkspace.name}</span>
          </span>
          <ChevronDown className={cn('h-icon w-icon shrink-0 text-muted-foreground transition-transform', open && 'rotate-180 text-primary-light')} />
        </span>
      </button>

      <div
        aria-hidden={!open}
        className={cn(
          'absolute left-0 right-0 top-full z-popover mt-ui-xs origin-top rounded-container border border-border bg-surface p-ui-xs shadow-popup transition-[opacity,transform] duration-150',
          open ? 'pointer-events-auto translate-y-0 opacity-100' : 'pointer-events-none -translate-y-1 opacity-0',
        )}
      >
        <div className="max-h-sidebar-context overflow-y-auto scrollbar-thin">
          <p className="px-ui-sm pb-ui-xs pt-ui-xs font-mono text-system-meta font-bold uppercase tracking-[0.14em] text-muted-foreground">Switch project</p>
          <div className="grid gap-ui-hairline">
            {projects.length === 0 ? (
              <p className="px-ui-sm py-ui-sm font-mono text-system-label text-muted-foreground">No projects available</p>
            ) : projects.map((project) => (
              <ContextMenuItem
                key={project.id}
                icon={FolderKanban}
                title={project.name}
                description={`/${project.slug}`}
                active={project.id === currentProject.id}
                onClick={() => handleProjectSelect(project)}
              />
            ))}
          </div>

          <div className="my-ui-xs border-t border-border pt-ui-xs">
            <ContextMenuItem icon={List} title="Manage projects" description="Select or create Projects" onClick={() => navigateAndClose(`/workspaces/${currentWorkspace.id}/projects`)} />
          </div>

          <div className="border-t border-border pt-ui-xs">
            <p className="px-ui-sm pb-ui-xs pt-ui-xs font-mono text-system-meta font-bold uppercase tracking-[0.14em] text-muted-foreground">Workspace</p>
            {workspaces.map((workspace) => (
              <ContextMenuItem
                key={workspace.id}
                icon={Building2}
                title={workspace.name}
                description={`/${workspace.slug}`}
                active={workspace.id === currentWorkspace.id}
                onClick={() => handleWorkspaceSelect(workspace)}
              />
            ))}
            <ContextMenuItem icon={List} title="Manage workspaces" description="Select or create Workspaces" onClick={() => navigateAndClose('/workspaces')} />
          </div>
        </div>
      </div>
    </div>
  )
}

function ConfigButton({ icon: Icon, label, description, onClick }: { icon: LucideIcon; label: string; description: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex min-h-control-nav w-full items-center gap-ui-sm rounded-technical border border-transparent px-ui-sm py-ui-sm text-left transition-colors hover:border-border hover:bg-accent/45"
    >
      <Icon className="h-icon w-icon shrink-0 text-muted-foreground transition-colors group-hover:text-slate-200" />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-mono text-system-control font-medium text-slate-300 transition-colors group-hover:text-slate-50">{label}</span>
        <span className="mt-ui-xs block truncate font-sans text-product-caption text-muted-foreground">{description}</span>
      </span>
    </button>
  )
}

function ProjectContextSkeleton() {
  return (
    <div className="space-y-ui-md" aria-label="Loading workspace">
      <div className="h-workspace-header animate-pulse rounded-container border border-border bg-control/40" />
      <div className="space-y-ui-hairline">
        <div className="h-control-nav animate-pulse rounded-technical bg-control/50" />
        <div className="h-control-nav animate-pulse rounded-technical bg-control/50" />
        <div className="h-control-nav animate-pulse rounded-technical bg-control/50" />
      </div>
    </div>
  )
}

function NoWorkspaceState() {
  return (
    <div className="rounded-container border border-border bg-control/35 p-ui-lg text-center">
      <p className="font-mono text-system-control font-bold text-slate-100">Workspace required</p>
      <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Select a Workspace before opening a Project.</p>
    </div>
  )
}

export function Sidebar() {
  const { pathname } = useLocation()
  const {
    workspaces,
    currentWorkspace,
    projects,
    currentProject,
    selectWorkspace,
    selectProject,
    isLoadingWorkspaces,
    isLoadingProjects,
  } = useWorkspace()
  const [showProjectSettings, setShowProjectSettings] = useState(false)
  const [showWorkspaceSettings, setShowWorkspaceSettings] = useState(false)
  const workspaceId = currentWorkspace?.id
  const projId = currentProject?.id
  const isProjectRoute = /^\/workspaces\/[^/]+\/projects\/[^/]+(?:\/|$)/.test(pathname)
  const isResolvingProjectContext = isProjectRoute && (
    isLoadingWorkspaces
    || isLoadingProjects
    || !currentWorkspace
    || !currentProject
  )

  return (
    <>
      <aside className="flex w-project-sidebar shrink-0 flex-col border-r border-border bg-surface">
        <header className="flex h-project-sidebar-header shrink-0 items-center gap-ui-sm border-b border-border px-ui-xl">
          <div className="flex h-control-sm w-control-sm items-center justify-center text-slate-50" aria-hidden="true">
            <Orbit className="h-icon-brand w-icon-brand" strokeWidth={1.7} />
          </div>
          <div className="min-w-0">
            <p className="font-mono text-heading-sm font-bold tracking-[0.02em] text-slate-50">WOOBE</p>
            <p className="mt-ui-hairline font-mono text-system-label uppercase tracking-[0.12em] text-muted-foreground">control plane</p>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
          <nav className="space-y-ui-xl px-ui-md py-ui-lg">
            {isResolvingProjectContext ? (
              <ProjectContextSkeleton />
            ) : !workspaceId || !currentWorkspace ? (
              <NoWorkspaceState />
            ) : projId && currentProject ? (
              <>
                <section>
                  <SidebarSectionTitle>Project</SidebarSectionTitle>
                  <ProjectContextCard
                    currentWorkspace={currentWorkspace}
                    currentProject={currentProject}
                    workspaces={workspaces}
                    projects={projects}
                    selectWorkspace={selectWorkspace}
                    selectProject={selectProject}
                  />
                </section>

                <ProjectNavGroup title="Build" items={buildNavItems} workspaceId={workspaceId} projId={projId} />
                <ProjectNavGroup title="Operate" items={operateNavItems} workspaceId={workspaceId} projId={projId} />
              </>
            ) : null}
          </nav>
        </div>

        {workspaceId && (
          <section className="border-t border-border px-ui-md py-ui-md">
            <SidebarSectionTitle>Config</SidebarSectionTitle>
            <div className="grid gap-ui-hairline">
              {projId && (
                <ConfigButton
                  icon={Settings}
                  label="Project settings"
                  description="Identity and project configuration"
                  onClick={() => setShowProjectSettings(true)}
                />
              )}
              <ConfigButton
                icon={Building2}
                label="Workspace settings"
                description="People, access and workspace configuration"
                onClick={() => setShowWorkspaceSettings(true)}
              />
            </div>
          </section>
        )}
        <SidebarUserCard variant="technical" />
      </aside>

      {workspaceId && projId && (
        <ProjectSettingsDialog
          open={showProjectSettings}
          workspaceId={workspaceId}
          projectId={projId}
          onClose={() => setShowProjectSettings(false)}
        />
      )}

      {workspaceId && (
        <WorkspaceSettingsDialog
          open={showWorkspaceSettings}
          workspaceId={workspaceId}
          onClose={() => setShowWorkspaceSettings(false)}
        />
      )}
    </>
  )
}
