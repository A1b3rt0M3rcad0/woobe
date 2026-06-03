import { Outlet } from 'react-router-dom'

export function DashboardShell() {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <Outlet />
    </div>
  )
}
