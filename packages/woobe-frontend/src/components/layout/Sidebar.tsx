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
    <p className="mb-2 px-2 font-mono text-[9px] font-bold uppercase tracking-[0.15em] text-muted">
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
          'group flex h-9 items-center gap-2.5 rounded-technical border px-2.5 font-mono text-[11px] transition-colors',
          isActive
            ? 'border-primary/45 bg-primary/[0.12] text-slate-50'
            : 'border-transparent text-slate-300 hover:border-border hover:bg-accent/45 hover:text-slate-50',
        )
      }
    >
      <Icon className="h-[15px] w-[15px] shrink-0 text-muted-foreground transition-colors group-hover:text-slate-200" />
      <span className="truncate">{item.label}</span>
    </NavLink>
  )
}

function ProjectNavGroup({ title, items, workspaceId, projId }: { title: string; items: NavItem[]; workspaceId: string; projId: string }) {
  return (
    <section>
      <SidebarSectionTitle>{title}</SidebarSectionTitle>
      <div className="grid gap-[3px]">
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
        'flex w-full items-start gap-2.5 rounded-control border px-2.5 py-2 text-left font-mono transition-colors',
        active
          ? 'border-primary/35 bg-primary/[0.1] text-slate-50'
          : 'border-transparent text-slate-300 hover:border-border hover:bg-control hover:text-slate-50',
      )}
    >
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[10px] font-medium">{title}</span>
        {description && <span className="mt-0.5 block truncate text-[8px] text-muted-foreground">{description}</span>}
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
  onWorkspaceSettings,
}: {
  currentWorkspace: WorkspaceShape
  currentProject: ProjectShape
  workspaces: WorkspaceShape[]
  projects: ProjectShape[]
  selectWorkspace: (workspace: WorkspaceShape) => void
  selectProject: (project: ProjectShape) => void
  onWorkspaceSettings: () => void
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

  const openWorkspaceSettings = () => {
    setOpen(false)
    onWorkspaceSettings()
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className={cn(
          'group w-full rounded-container border bg-control/45 px-3 py-2.5 text-left transition-colors',
          open ? 'border-primary/40 bg-primary/[0.08]' : 'border-border hover:border-slate-600 hover:bg-control',
        )}
      >
        <span className="flex items-center justify-between gap-2">
          <span className="min-w-0 flex-1">
            <span className="block truncate font-mono text-[11px] font-bold text-slate-50">{currentProject.name}</span>
            <span className="mt-0.5 block truncate font-mono text-[8px] text-muted-foreground">{currentWorkspace.name}</span>
          </span>
          <ChevronDown className={cn('h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180 text-primary-light')} />
        </span>
      </button>

      <div
        aria-hidden={!open}
        className={cn(
          'absolute left-0 right-0 top-full z-40 mt-1.5 origin-top rounded-container border border-border bg-surface p-1.5 shadow-[0_12px_36px_rgba(0,0,0,0.28)] transition-[opacity,transform] duration-150',
          open ? 'pointer-events-auto translate-y-0 opacity-100' : 'pointer-events-none -translate-y-1 opacity-0',
        )}
      >
        <div className="max-h-[420px] overflow-y-auto scrollbar-thin">
          <p className="px-2 pb-1.5 pt-1 font-mono text-[8px] font-bold uppercase tracking-[0.14em] text-muted">Switch project</p>
          <div className="grid gap-[2px]">
            {projects.length === 0 ? (
              <p className="px-2 py-2 font-mono text-[9px] text-muted-foreground">No projects available</p>
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

          <div className="my-1.5 border-t border-border pt-1.5">
            <ContextMenuItem icon={List} title="Manage projects" description="Select or create Projects" onClick={() => navigateAndClose(`/workspaces/${currentWorkspace.id}/projects`)} />
            <ContextMenuItem icon={Settings} title="Project settings" description="Configure this Project" onClick={() => navigateAndClose(`/workspaces/${currentWorkspace.id}/projects/${currentProject.id}/settings`)} />
          </div>

          <div className="border-t border-border pt-1.5">
            <p className="px-2 pb-1.5 pt-1 font-mono text-[8px] font-bold uppercase tracking-[0.14em] text-muted">Workspace</p>
            <ContextMenuItem icon={Settings} title="Workspace settings" description="People, access and configuration" onClick={openWorkspaceSettings} />
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

function ProjectContextSkeleton() {
  return (
    <div className="space-y-3" aria-label="Loading workspace">
      <div className="h-[54px] animate-pulse rounded-container border border-border bg-control/40" />
      <div className="space-y-[3px]">
        <div className="h-9 animate-pulse rounded-technical bg-control/50" />
        <div className="h-9 animate-pulse rounded-technical bg-control/50" />
        <div className="h-9 animate-pulse rounded-technical bg-control/50" />
      </div>
    </div>
  )
}

function NoWorkspaceState() {
  return (
    <div className="rounded-container border border-border bg-control/35 p-4 text-center">
      <p className="font-mono text-[10px] font-bold text-slate-100">Workspace required</p>
      <p className="mt-1 font-mono text-[8px] leading-4 text-muted-foreground">Select a Workspace before opening a Project.</p>
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
      <aside className="flex w-[258px] shrink-0 flex-col border-r border-border bg-surface">
        <header className="flex h-[72px] shrink-0 items-center gap-2.5 border-b border-border px-[18px]">
          <div className="flex h-[29px] w-[29px] items-center justify-center text-slate-50" aria-hidden="true">
            <Orbit className="h-[21px] w-[21px]" strokeWidth={1.7} />
          </div>
          <div className="min-w-0">
            <p className="font-mono text-sm font-bold tracking-[0.02em] text-slate-50">WOOBE</p>
            <p className="mt-px font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">control plane</p>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
          <nav className="space-y-5 px-3 py-4">
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
                    onWorkspaceSettings={() => setShowWorkspaceSettings(true)}
                  />
                </section>

                <ProjectNavGroup title="Build" items={buildNavItems} workspaceId={workspaceId} projId={projId} />
                <ProjectNavGroup title="Operate" items={operateNavItems} workspaceId={workspaceId} projId={projId} />
              </>
            ) : null}
          </nav>
        </div>

        {workspaceId && (
          <section className="border-t border-border px-3 py-3">
            <SidebarSectionTitle>Workspace</SidebarSectionTitle>
            <button
              type="button"
              onClick={() => setShowWorkspaceSettings(true)}
              className="group flex h-9 w-full items-center gap-2.5 rounded-technical border border-transparent px-2.5 text-left font-mono text-[11px] text-slate-300 transition-colors hover:border-border hover:bg-accent/45 hover:text-slate-50"
            >
              <Building2 className="h-[15px] w-[15px] shrink-0 text-muted-foreground group-hover:text-slate-200" />
              <span className="truncate">Workspace</span>
            </button>
          </section>
        )}
        <SidebarUserCard variant="technical" />
      </aside>

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
