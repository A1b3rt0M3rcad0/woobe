import { NavLink, useLocation } from 'react-router-dom'
import {
  Activity,
  BarChart3,
  BookOpen,
  Bot,
  Boxes,
  Cable,
  FolderKanban,
  Key,
  LayoutDashboard,
  MessageSquare,
  Play,
  Settings,
  Workflow,
  Wrench,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { workspaceProjectPath } from '@/lib/constants/routes'
import { SidebarUserCard } from './SidebarUserCard'

interface NavItem {
  label: string
  icon: LucideIcon
  segment?: string
}

const buildItems: NavItem[] = [
  { label: 'Overview', icon: LayoutDashboard },
  { label: 'Network', icon: Workflow, segment: 'networks' },
  { label: 'Agents', icon: Bot, segment: 'agents' },
  { label: 'Knowledge', icon: BookOpen, segment: 'knowledge' },
  { label: 'Tools', icon: Wrench, segment: 'tools' },
  { label: 'Models', icon: Boxes, segment: 'models' },
  { label: 'Credentials', icon: Cable, segment: 'credentials' },
]

const operateItems: NavItem[] = [
  { label: 'ChatSurfaces', icon: MessageSquare, segment: 'chat-surfaces' },
  { label: 'API Keys', icon: Key, segment: 'api-keys' },
  { label: 'Usage', icon: BarChart3, segment: 'usage' },
  { label: 'Traces', icon: Activity, segment: 'traces' },
]

function Section({ title, items, workspaceId, projectId }: { title: string; items: NavItem[]; workspaceId: string; projectId: string }) {
  return (
    <section className="space-y-2">
      <p className="px-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted/80">{title}</p>
      <div className="space-y-1">
        {items.map((item) => {
          const href = workspaceProjectPath(workspaceId, projectId, ...(item.segment ? [item.segment] : []))
          const Icon = item.icon
          return (
            <NavLink
              key={item.label}
              to={href}
              end={!item.segment}
              className={({ isActive }) => cn(
                'flex items-center gap-3 rounded-xl border px-3 py-2 text-sm font-medium',
                isActive ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:bg-background/70 hover:text-white',
              )}
            >
              <Icon className="h-4 w-4" />{item.label}
            </NavLink>
          )
        })}
      </div>
    </section>
  )
}

export function Sidebar() {
  const { pathname } = useLocation()
  const { currentWorkspace, currentProject } = useWorkspace()
  const workspaceId = currentWorkspace?.id
  const projectId = currentProject?.id
  const isProjectRoute = /^\/workspaces\/[^/]+\/projects\/[^/]+(?:\/|$)/.test(pathname)

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-surface">
      <div className="border-b border-border p-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light"><Play className="h-4 w-4 fill-current" /></div>
          <div><p className="text-sm font-semibold text-white">Woobe</p><p className="text-xs text-muted">Control plane</p></div>
        </div>
      </div>
      <ScrollArea className="flex-1">
        <nav className="space-y-5 p-3">
          <NavLink to="/workspaces" className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted hover:bg-background/70 hover:text-white">
            <Boxes className="h-4 w-4" />Workspaces
          </NavLink>
          {workspaceId && (
            <NavLink to={`/workspaces/${workspaceId}/projects`} className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted hover:bg-background/70 hover:text-white">
              <FolderKanban className="h-4 w-4" />Projects
            </NavLink>
          )}
          {isProjectRoute && workspaceId && projectId && (
            <>
              <Section title="Build" items={buildItems} workspaceId={workspaceId} projectId={projectId} />
              <Section title="Operate" items={operateItems} workspaceId={workspaceId} projectId={projectId} />
              <NavLink to={`/workspaces/${workspaceId}/projects/${projectId}/settings`} className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted hover:bg-background/70 hover:text-white">
                <Settings className="h-4 w-4" />Project settings
              </NavLink>
            </>
          )}
          {workspaceId && (
            <NavLink to={`/workspaces/${workspaceId}/settings`} className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted hover:bg-background/70 hover:text-white">
              <Settings className="h-4 w-4" />Workspace settings
            </NavLink>
          )}
        </nav>
      </ScrollArea>
      <SidebarUserCard />
    </aside>
  )
}
