import { Check, ShieldCheck } from 'lucide-react'
import { Badge, TechnicalListItem } from '@woobe/ui'
import type { AuthorityCategory } from './api'

const descriptions: Record<string, string> = {
  'project-reader': 'Read resources without edits or secrets.',
  'agent-editor': 'Create and edit Agents.',
  'network-editor': 'Create and edit Networks.',
  'knowledge-editor': 'Manage Knowledge collections.',
  'version-builder': 'Manage Agent and Network versions.',
  'production-publisher': 'Publish Agents and Networks to production.',
  'runtime-observer': 'Read Runs, observability and usage.',
  'project-administrator': 'Full management of this Project.',
  'workspace-key-manager': 'Manage Workspace Control Keys.',
}

export function roleName(name: string) {
  return name
    .replaceAll('-', ' ')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function constrainedConditions(
  role: Record<string, string[]>,
  inherited: Record<string, string[]>,
) {
  const conditions: Record<string, string[]> = { ...role, ...inherited }
  for (const key of Object.keys(role)) {
    if (!inherited[key]) continue
    const intersection = role[key].filter((value) =>
      inherited[key].includes(value),
    )
    if (!intersection.length) return null
    conditions[key] = intersection
  }
  return conditions
}

export function AccessRolePicker({
  roles,
  permissions,
  conditions = {},
  selectedId,
  custom,
  onSelect,
  onCustom,
}: {
  roles: AuthorityCategory[]
  permissions: string[]
  conditions?: Record<string, string[]>
  selectedId?: string
  custom: boolean
  onSelect: (role: AuthorityCategory) => void
  onCustom: () => void
}) {
  return (
    <div
      className="scrollbar-thin grid max-h-48 grid-cols-2 gap-ui-xs overflow-y-auto pr-ui-xs lg:grid-cols-3"
      role="group"
      aria-label="Predefined access roles"
    >
      {roles
        .filter((role) => role.status === 'active')
        .map((role) => {
          const selected = role.id === selectedId && !custom
          const allowed =
            role.permissions.every((permission) =>
              permissions.includes(permission),
            ) &&
            constrainedConditions(role.conditions, conditions) !== null &&
            (role.scope !== 'workspace' ||
              Object.keys(role.conditions).length === 0)
          return (
            <TechnicalListItem
              key={role.id}
              label={roleName(role.name)}
              aria-label={roleName(role.name)}
              aria-pressed={selected}
              selected={selected}
              disabled={!allowed}
              description={
                allowed
                  ? role.description ||
                    descriptions[role.name] ||
                    `${role.permissions.length} permissions`
                  : 'Exceeds your delegable access.'
              }
              descriptionVariant="product"
              density="compact"
              multiline
              className="h-full items-start"
              trailing={
                selected ? (
                  <Check className="h-icon-sm w-icon-sm text-primary-light" />
                ) : undefined
              }
              onClick={() => onSelect(role)}
            />
          )
        })}
      <TechnicalListItem
        label="Custom access"
        aria-label="Custom access"
        aria-pressed={custom}
        selected={custom}
        description="Advanced permission selection."
        density="compact"
        multiline
        className="h-full items-start"
        onClick={onCustom}
      />
    </div>
  )
}

export function RoleSummary({ role }: { role: AuthorityCategory | undefined }) {
  if (!role) return null
  return (
    <div className="flex flex-wrap items-center gap-ui-sm border-t border-border pt-ui-sm text-system-meta text-muted-foreground">
      <ShieldCheck className="h-icon-sm w-icon-sm text-primary-light" />
      <span>{roleName(role.name)}</span>
      <Badge variant="outline" size="compact">
        Revision {role.revision}
      </Badge>
      <details className="min-w-0">
        <summary className="cursor-pointer">
          {role.permissions.length} permissions
        </summary>
        <p className="mt-ui-xs break-all font-mono">
          {role.permissions.join(', ')}
        </p>
      </details>
    </div>
  )
}
