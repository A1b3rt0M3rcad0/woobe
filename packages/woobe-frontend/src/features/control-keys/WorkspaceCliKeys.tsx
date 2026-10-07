import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, FolderKanban, KeyRound, ShieldCheck } from 'lucide-react'
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Checkbox,
  CodePanel,
  EmptyStatePanel,
  Field,
  FieldLabel,
  Input,
  SectionBlock,
  SegmentedControl,
  WoobeDatePicker,
  formatWoobeDate,
  TechnicalListItem,
} from '@woobe/ui'
import { CopyButton } from '@/components/common/CopyButton'
import { defaultExpirationDate, expirationAfterDate } from './expiration'
import {
  AccessRolePicker,
  RoleSummary,
  constrainedConditions,
} from './AccessRolePicker'
import { API_BASE_URL } from '@/lib/api/client'
import type { Project } from '@/features/projects/types'
import {
  createControlKey,
  getEffectiveAccess,
  getPermissionCatalog,
  listAuthorityCategories,
  listControlKeys,
  revokeControlKey,
  rotateControlKey,
  type ControlKey,
  type AuthorityCategory,
  type IssuedControlKey,
  type ProjectGrant,
} from './api'

function permissionName(value: string) {
  return value
    .replaceAll('_', ' ')
    .replaceAll(':', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function PermissionChoices({
  title,
  permissions,
  selected,
  onChange,
}: {
  title: string
  permissions: string[]
  selected: string[]
  onChange: (value: string[]) => void
}) {
  const groups = new Map<string, string[]>()
  for (const permission of permissions) {
    const family = permission.slice(0, permission.lastIndexOf(':'))
    groups.set(family, [...(groups.get(family) ?? []), permission])
  }
  return (
    <div className="grid min-w-0 gap-ui-sm">
      <div className="flex flex-wrap items-center justify-between gap-ui-xs">
        <p className="font-mono text-system-label text-muted-foreground">
          {title}
        </p>
        <Badge variant="outline" size="compact">
          {selected.length} selected
        </Badge>
      </div>
      <div className="flex flex-wrap gap-ui-xs">
        <Button
          size="sm"
          variant="outline"
          onClick={() =>
            onChange(
              permissions.filter(
                (value) =>
                  value.endsWith(':read') && !value.startsWith('secret:'),
              ),
            )
          }
        >
          Read permissions
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onChange(permissions)}
        >
          All available permissions
        </Button>
        <Button size="sm" variant="ghost" onClick={() => onChange([])}>
          Clear
        </Button>
      </div>
      <div className="scrollbar-thin grid max-h-60 gap-ui-md overflow-y-auto pr-ui-xs">
        {[...groups].map(([family, items]) => (
          <div key={family} className="grid gap-ui-xs">
            <p className="font-mono text-system-meta uppercase tracking-ui-eyebrow text-muted-foreground">
              {permissionName(family)}
            </p>
            <div className="grid gap-ui-xs sm:grid-cols-2">
              {items.map((permission) => {
                const checked = selected.includes(permission)
                return (
                  <label
                    key={permission}
                    className={`flex min-w-0 cursor-pointer items-center gap-ui-sm rounded-control border p-ui-sm transition-colors ${checked ? 'border-primary/40 bg-primary/10' : 'border-border bg-control hover:border-primary/30'}`}
                  >
                    <Checkbox
                      aria-label={permission}
                      checked={checked}
                      onChange={() =>
                        onChange(
                          checked
                            ? selected.filter((value) => value !== permission)
                            : [...selected, permission],
                        )
                      }
                    />
                    <span className="min-w-0">
                      <span className="block text-system-label font-medium">
                        {permissionName(
                          permission.slice(permission.lastIndexOf(':') + 1),
                        )}
                      </span>
                      <span className="block truncate font-mono text-system-meta text-muted-foreground">
                        {permission}
                      </span>
                    </span>
                  </label>
                )
              })}
            </div>
          </div>
        ))}
        {!permissions.length ? (
          <EmptyStatePanel compact title="No delegable permissions" />
        ) : null}
      </div>
    </div>
  )
}

function ProjectPermissions({
  workspaceId,
  project,
  catalog,
  roles,
  grant,
  onChange,
}: {
  workspaceId: string
  project: Project
  catalog: string[]
  roles: AuthorityCategory[]
  grant?: ProjectGrant
  onChange: (grant: ProjectGrant) => void
}) {
  const [custom, setCustom] = useState(
    Boolean(grant?.permissions.length && !grant.category_id),
  )
  const access = useQuery({
    queryKey: ['effective-access', workspaceId, project.id],
    queryFn: () => getEffectiveAccess(workspaceId, project.id),
    retry: false,
  })
  if (access.isPending) return <p role="status">Loading Project access…</p>
  if (access.isError)
    return (
      <p role="alert">Unable to load delegable access for {project.name}.</p>
    )
  return (
    <div className="grid gap-ui-sm">
      <AccessRolePicker
        roles={roles}
        permissions={access.data.permissions}
        conditions={access.data.conditions}
        selectedId={grant?.category_id}
        custom={custom}
        onSelect={(role) => {
          const conditions = constrainedConditions(
            role.conditions,
            access.data.conditions,
          )
          if (!conditions) return
          setCustom(false)
          onChange({
            project_id: project.id,
            permissions: role.permissions,
            conditions,
            category_id: role.id,
            category_revision: role.revision,
          })
        }}
        onCustom={() => {
          setCustom(true)
          onChange({
            project_id: project.id,
            permissions: grant?.permissions ?? [],
            conditions: access.data.conditions,
          })
        }}
      />
      {custom ? (
        <PermissionChoices
          title="Custom Project permissions"
          permissions={catalog.filter((permission) =>
            access.data.permissions.includes(permission),
          )}
          selected={grant?.permissions ?? []}
          onChange={(permissions) =>
            onChange({
              project_id: project.id,
              permissions,
              conditions: access.data.conditions,
            })
          }
        />
      ) : (
        <RoleSummary
          role={roles.find((role) => role.id === grant?.category_id)}
        />
      )}
      {Object.keys(access.data.conditions).length ? (
        <p className="text-system-meta text-muted-foreground">
          Your existing access restrictions also apply.
        </p>
      ) : null}
    </div>
  )
}

function date(value?: string | null, expiration = false) {
  return value
    ? formatWoobeDate(new Date(Date.parse(value) - (expiration ? 1 : 0)))
    : 'Never'
}

export function WorkspaceCliKeys({
  workspaceId,
  projects,
  onConfigurationChange,
}: {
  workspaceId: string
  projects: Project[]
  onConfigurationChange?: (active: boolean) => void
}) {
  const queryClient = useQueryClient()
  const access = useQuery({
    queryKey: ['effective-access', workspaceId],
    queryFn: () => getEffectiveAccess(workspaceId),
    retry: false,
  })
  const permissions = access.data?.permissions ?? []
  const canRead = permissions.includes('keys:read')
  const catalog = useQuery({
    queryKey: ['permission-catalog'],
    queryFn: getPermissionCatalog,
    enabled: canRead,
    retry: false,
  })
  const keys = useQuery({
    queryKey: ['control-keys', workspaceId],
    queryFn: () => listControlKeys(workspaceId),
    enabled: canRead,
    retry: false,
  })
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const roles = useQuery({
    queryKey: ['authority-categories', workspaceId],
    queryFn: () => listAuthorityCategories(workspaceId),
    enabled: canRead && creating,
    retry: false,
  })
  const [expirationDate, setExpirationDate] = useState<Date | null>(() =>
    defaultExpirationDate(),
  )
  const [expirationPreset, setExpirationPreset] = useState('90d')
  const expiresAt = useMemo(
    () => expirationAfterDate(expirationDate),
    [expirationDate],
  )
  const [workspaceRole, setWorkspaceRole] = useState<AuthorityCategory | null>(
    null,
  )
  const [customWorkspace, setCustomWorkspace] = useState(false)
  const [permissionScope, setPermissionScope] = useState(
    projects.length ? 'projects' : 'workspace',
  )
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const selectedProject =
    projects.find((project) => project.id === selectedProjectId) ?? projects[0]
  const [workspacePermissions, setWorkspacePermissions] = useState<string[]>([])
  const [creationPermissions, setCreationPermissions] = useState<string[]>([])
  const [grants, setGrants] = useState<ProjectGrant[]>([])
  const [issued, setIssued] = useState<IssuedControlKey | null>(null)
  useEffect(() => {
    onConfigurationChange?.(creating || Boolean(issued))
  }, [creating, issued, onConfigurationChange])
  useEffect(() => () => onConfigurationChange?.(false), [onConfigurationChange])
  const [action, setAction] = useState<{
    kind: 'rotate' | 'revoke'
    key: ControlKey
  } | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)
  const attempt = useRef<{ signature: string; id: string } | null>(null)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  function idempotencyKey(signature: string) {
    if (attempt.current?.signature !== signature)
      attempt.current = { signature, id: crypto.randomUUID() }
    return attempt.current.id
  }

  async function refreshKeys() {
    await queryClient.invalidateQueries({
      queryKey: ['control-keys', workspaceId],
    })
  }

  async function submitCreate() {
    if (
      pending ||
      !name.trim() ||
      !catalog.data ||
      !roles.data ||
      (!workspacePermissions.length &&
        !grants.some((grant) => grant.permissions.length))
    )
      return
    setPending(true)
    setError(null)
    try {
      const body = {
        name: name.trim(),
        description: description.trim() || null,
        expires_at: expiresAt?.toISOString() ?? null,
        permissions: workspacePermissions,
        ...(workspaceRole
          ? {
              category_id: workspaceRole.id,
              category_revision: workspaceRole.revision,
            }
          : {}),
        project_grants: grants.filter((grant) => grant.permissions.length > 0),
        on_project_create_permissions: workspacePermissions.includes(
          'projects:create',
        )
          ? creationPermissions
          : [],
      }
      const result = await createControlKey(
        workspaceId,
        body,
        idempotencyKey(JSON.stringify(body)),
      )
      if (mounted.current) {
        setIssued(result)
        setCreating(false)
        setName('')
        setDescription('')
        setExpirationDate(defaultExpirationDate())
        setExpirationPreset('90d')
        setWorkspaceRole(null)
        setCustomWorkspace(false)
        setWorkspacePermissions([])
        setCreationPermissions([])
        setGrants([])
        attempt.current = null
      }
      await refreshKeys()
    } catch (failure) {
      if (mounted.current)
        setError(
          failure instanceof Error
            ? failure.message
            : 'Unable to create CLI key',
        )
    } finally {
      if (mounted.current) setPending(false)
    }
  }

  async function confirmAction() {
    if (!action || pending) return
    setPending(true)
    setError(null)
    try {
      if (action.kind === 'rotate') {
        const result = await rotateControlKey(
          workspaceId,
          action.key,
          idempotencyKey(`rotate:${action.key.id}:${action.key.etag}`),
        )
        if (mounted.current) setIssued(result)
      } else {
        await revokeControlKey(workspaceId, action.key)
      }
      if (mounted.current) {
        setAction(null)
        attempt.current = null
      }
      await refreshKeys()
    } catch (failure) {
      if (mounted.current)
        setError(
          failure instanceof Error
            ? failure.message
            : 'Unable to update CLI key',
        )
      await refreshKeys()
      // An observed stale revision must be selected again before another mutation.
      if (mounted.current) setAction(null)
    } finally {
      if (mounted.current) setPending(false)
    }
  }

  if (access.isPending) return <p role="status">Loading CLI key access…</p>
  if (access.isError)
    return (
      <Alert variant="destructive">
        <AlertTitle>Unable to check CLI key access</AlertTitle>
        <AlertDescription>{access.error.message}</AlertDescription>
        <Button variant="outline" onClick={() => void access.refetch()}>
          Retry
        </Button>
      </Alert>
    )
  if (!canRead)
    return (
      <EmptyStatePanel
        icon={<KeyRound className="h-icon-lg w-icon-lg" />}
        title="CLI key management is restricted"
        description="A Workspace owner or an admin with key-management permissions can manage Control Keys."
      />
    )

  if (issued)
    return (
      <div className="grid gap-ui-md">
        <Alert variant="warning">
          <AlertTitle>Copy this key now</AlertTitle>
          <AlertDescription>
            This secret is shown only in this view. Closing it removes the
            secret from the interface; rotate the key if you lose it.
          </AlertDescription>
        </Alert>
        <SectionBlock title="CLI Control Key ready" description={issued.name}>
          <CodePanel
            title="Control Key"
            badge="One-time reveal"
            actions={<CopyButton text={issued.key} label="Copy Control Key" />}
          >
            <code className="block break-all p-ui-md font-mono text-system-control">
              {issued.key}
            </code>
          </CodePanel>
        </SectionBlock>
        <SectionBlock
          title="Connect woobe-cli"
          description="Create a connection, activate it, then paste the CLI Key at the masked prompt. The CLI discovers your Workspace and granted Projects automatically."
        >
          <CodePanel
            title="CLI setup"
            actions={<CopyButton text={`woobe context create woobe --api-url ${API_BASE_URL}\nwoobe context use woobe\nwoobe auth login --cli-key`} />}
          >
            <pre className="overflow-x-auto p-ui-md font-mono text-system-label">{`woobe context create woobe --api-url ${API_BASE_URL}\nwoobe context use woobe\nwoobe auth login --cli-key`}</pre>
          </CodePanel>
          <p className="mt-ui-sm text-system-label text-muted-foreground">
            One granted Project is selected automatically. With several Projects,
            choose one by name. To switch later, run{' '}
            <code>woobe context project select</code>. Works on Windows, Linux and
            macOS. Runtime execution uses a separate Runtime Key.
          </p>
        </SectionBlock>
        <div className="flex justify-end">
          <Button onClick={() => setIssued(null)}>I saved the key</Button>
        </div>
      </div>
    )

  return (
    <div className="grid gap-ui-md">
      {creating ? (
        <div className="flex items-center justify-between gap-ui-sm">
          <h3 className="font-mono text-section-title font-semibold">
            Create CLI key
          </h3>
          <Badge variant="outline" size="compact">
            Control Key
          </Badge>
        </div>
      ) : (
        <SectionBlock
          title="CLI Keys"
          description="Manage credentials for woobe-cli and automation in this Workspace."
          actions={
            permissions.includes('keys:create') ? (
              <Button
                onClick={() => {
                  setCreating(true)
                  setName('')
                  setDescription('')
                  setWorkspacePermissions([])
                  setCreationPermissions([])
                  setGrants([])
                  attempt.current = null
                  setExpirationDate(defaultExpirationDate())
                  setExpirationPreset('90d')
                  setWorkspaceRole(null)
                  setCustomWorkspace(false)
                  setPermissionScope(projects.length ? 'projects' : 'workspace')
                  setError(null)
                }}
              >
                Create CLI key
              </Button>
            ) : undefined
          }
        />
      )}
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>CLI key operation failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {creating ? (
        <div className="grid gap-ui-md">
          <SectionBlock
            title="Key identity"
            eyebrow="01 · Integration"
            density="compact"
            className="p-ui-sm"
          >
            <div className="grid gap-ui-md sm:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
              <Field>
                <FieldLabel htmlFor="cli-key-name">Name</FieldLabel>
                <Input
                  id="cli-key-name"
                  value={name}
                  maxLength={255}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="My workstation"
                  autoFocus
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="cli-key-description">
                  Description{' '}
                  <span className="font-normal text-muted-foreground">
                    Optional
                  </span>
                </FieldLabel>
                <Input
                  id="cli-key-description"
                  value={description}
                  maxLength={500}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="Which workstation, service or automation uses this key?"
                />
              </Field>
            </div>
          </SectionBlock>
          <div className="grid items-stretch gap-ui-md md:grid-cols-[minmax(0,1.7fr)_minmax(20rem,1fr)]">
            <SectionBlock
              title="Roles and access"
              eyebrow="02 · Authorization"
              density="compact"
              className="min-w-0"
              actions={
                <ShieldCheck className="h-icon w-icon text-primary-light" />
              }
            >
              <div className="grid gap-ui-sm">
                <div className="max-w-full overflow-x-auto">
                  <SegmentedControl
                    ariaLabel="CLI key permission scope"
                    size="compact"
                    items={[
                      {
                        value: 'projects',
                        label: `Projects (${grants.filter((grant) => grant.permissions.length).length})`,
                      },
                      { value: 'workspace', label: 'Workspace' },
                      ...(workspacePermissions.includes('projects:create')
                        ? [{ value: 'new-projects', label: 'New Projects' }]
                        : []),
                    ]}
                    value={permissionScope}
                    onValueChange={setPermissionScope}
                  />
                </div>
                {roles.isError || catalog.isError ? (
                  <Alert variant="destructive">
                    <AlertTitle>Unable to load access roles</AlertTitle>
                    <Button
                      variant="outline"
                      onClick={() => {
                        void roles.refetch()
                        void catalog.refetch()
                      }}
                    >
                      Retry
                    </Button>
                  </Alert>
                ) : !roles.data || !catalog.data ? (
                  <p role="status">Loading access roles…</p>
                ) : permissionScope === 'workspace' ? (
                  <>
                    <AccessRolePicker
                      roles={roles.data.filter(
                        (role) => role.scope === 'workspace',
                      )}
                      permissions={permissions}
                      selectedId={workspaceRole?.id}
                      custom={customWorkspace}
                      onSelect={(role) => {
                        setWorkspaceRole(role)
                        setCustomWorkspace(false)
                        setWorkspacePermissions(role.permissions)
                        if (!role.permissions.includes('projects:create'))
                          setCreationPermissions([])
                      }}
                      onCustom={() => {
                        setWorkspaceRole(null)
                        setCustomWorkspace(true)
                      }}
                    />
                    {customWorkspace ? (
                      <PermissionChoices
                        title="Custom Workspace permissions"
                        permissions={catalog.data.permissions.workspace.filter(
                          (permission) => permissions.includes(permission),
                        )}
                        selected={workspacePermissions}
                        onChange={(value) => {
                          setWorkspacePermissions(value)
                          if (!value.includes('projects:create'))
                            setCreationPermissions([])
                        }}
                      />
                    ) : (
                      <RoleSummary role={workspaceRole ?? undefined} />
                    )}
                    {workspacePermissions.length ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="justify-self-start"
                        onClick={() => {
                          setWorkspaceRole(null)
                          setWorkspacePermissions([])
                          setCreationPermissions([])
                          setCustomWorkspace(false)
                        }}
                      >
                        Remove Workspace access
                      </Button>
                    ) : null}
                  </>
                ) : permissionScope === 'new-projects' &&
                  workspacePermissions.includes('projects:create') ? (
                  <PermissionChoices
                    title="Permissions on newly created Projects"
                    permissions={catalog.data.permissions.project}
                    selected={creationPermissions}
                    onChange={setCreationPermissions}
                  />
                ) : (
                  <>
                    <div
                      className="flex gap-ui-xs overflow-x-auto pb-ui-xs"
                      role="group"
                      aria-label="Choose a Project"
                    >
                      {projects.map((project) => (
                        <Button
                          key={project.id}
                          size="sm"
                          variant={
                            selectedProject?.id === project.id
                              ? 'secondary'
                              : 'outline'
                          }
                          aria-label={`Project: ${project.name}`}
                          aria-pressed={selectedProject?.id === project.id}
                          className="shrink-0"
                          onClick={() => setSelectedProjectId(project.id)}
                        >
                          <FolderKanban className="mr-ui-xs h-icon-sm w-icon-sm" />
                          {project.name}
                          {grants.some(
                            (grant) =>
                              grant.project_id === project.id &&
                              grant.permissions.length,
                          ) ? (
                            <Check className="ml-ui-xs h-icon-sm w-icon-sm text-primary-light" />
                          ) : null}
                        </Button>
                      ))}
                      {grants.some(
                        (grant) =>
                          grant.project_id === selectedProject?.id &&
                          grant.permissions.length,
                      ) ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="shrink-0"
                          onClick={() =>
                            setGrants((current) =>
                              current.filter(
                                (grant) =>
                                  grant.project_id !== selectedProject?.id,
                              ),
                            )
                          }
                        >
                          Remove Project access
                        </Button>
                      ) : null}
                    </div>
                    {selectedProject ? (
                      <ProjectPermissions
                        key={selectedProject.id}
                        workspaceId={workspaceId}
                        project={selectedProject}
                        roles={roles.data.filter(
                          (role) => role.scope === 'project',
                        )}
                        catalog={catalog.data.permissions.project}
                        grant={grants.find(
                          (grant) => grant.project_id === selectedProject.id,
                        )}
                        onChange={(grant) =>
                          setGrants((current) => [
                            ...current.filter(
                              (item) => item.project_id !== grant.project_id,
                            ),
                            grant,
                          ])
                        }
                      />
                    ) : (
                      <EmptyStatePanel
                        compact
                        title="No Projects available"
                        description="Select a Workspace role to continue."
                      />
                    )}
                  </>
                )}
              </div>
            </SectionBlock>
            <SectionBlock
              title="Expiration"
              eyebrow="03 · Validity"
              density="compact"
              className="min-w-0"
            >
              <div className="grid gap-ui-sm">
                <div className="overflow-x-auto">
                  <SegmentedControl
                    ariaLabel="CLI key expiration"
                    size="compact"
                    value={expirationPreset}
                    items={[
                      { value: '7d', label: '7 days' },
                      { value: '30d', label: '30 days' },
                      { value: '90d', label: '90 days' },
                      { value: 'never', label: 'No expiration' },
                    ]}
                    onValueChange={(value) => {
                      setExpirationPreset(value)
                      setExpirationDate(
                        value === 'never'
                          ? null
                          : defaultExpirationDate(Number(value.slice(0, -1))),
                      )
                    }}
                  />
                </div>
                <WoobeDatePicker
                  value={expirationDate}
                  onChange={(date) => {
                    setExpirationDate(date)
                    setExpirationPreset('custom')
                  }}
                />
                <p className="text-system-meta text-muted-foreground">
                  {expirationDate
                    ? `Valid through ${formatWoobeDate(expirationDate)}. The entire selected day is included.`
                    : 'Active until revoked. Choose a calendar day to set an expiration.'}
                </p>
              </div>
            </SectionBlock>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-ui-sm border-t border-border pt-ui-md">
            <p className="text-system-label text-muted-foreground">
              {workspacePermissions.length} Workspace permissions ·{' '}
              {grants.filter((grant) => grant.permissions.length > 0).length}{' '}
              Project grants
            </p>
            <div className="flex gap-ui-sm">
              <Button
                variant="outline"
                disabled={pending}
                onClick={() => setCreating(false)}
              >
                Cancel
              </Button>
              <Button
                loading={pending}
                disabled={
                  !name.trim() ||
                  !catalog.data ||
                  !roles.data ||
                  (!workspacePermissions.length &&
                    !grants.some((grant) => grant.permissions.length)) ||
                  (expiresAt !== null && expiresAt.getTime() <= Date.now())
                }
                onClick={() => void submitCreate()}
              >
                Create key
              </Button>
            </div>
          </div>
        </div>
      ) : null}
      {action ? (
        <Alert variant="warning">
          <AlertTitle>
            {action.kind === 'rotate' ? 'Rotate' : 'Revoke'} {action.key.name}?
          </AlertTitle>
          <AlertDescription>
            {action.kind === 'rotate'
              ? 'The current key stops working immediately. Save the replacement key and update your CLI credential.'
              : 'This key will stop working immediately. This action cannot be undone.'}
          </AlertDescription>
          <div className="mt-ui-sm flex gap-ui-sm">
            <Button
              variant="outline"
              disabled={pending}
              onClick={() => setAction(null)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              loading={pending}
              onClick={() => void confirmAction()}
            >
              Confirm {action.kind === 'rotate' ? 'rotation' : 'revocation'}
            </Button>
          </div>
        </Alert>
      ) : null}
      {creating ? null : keys.isPending ? (
        <p role="status">Loading CLI keys…</p>
      ) : keys.isError ? (
        <Alert variant="destructive">
          <AlertTitle>Unable to load CLI keys</AlertTitle>
          <AlertDescription>{keys.error.message}</AlertDescription>
          <Button variant="outline" onClick={() => void keys.refetch()}>
            Retry
          </Button>
        </Alert>
      ) : (
        <div className="grid gap-ui-sm">
          {keys.data.length === 0 ? (
            <EmptyStatePanel
              compact
              title="No CLI keys yet"
              description="Create a Control Key to connect woobe-cli to this Workspace."
            />
          ) : null}
          {keys.data.map((key) => {
            const active =
              key.status === 'active' &&
              (!key.expires_at ||
                new Date(key.expires_at).getTime() > Date.now())
            return (
              <SectionBlock
                key={key.id}
                title={key.name}
                description={key.description ?? key.key_prefix}
                actions={
                  <Badge variant={active ? 'success' : 'outline'}>
                    {key.status === 'active' && !active
                      ? 'expired'
                      : key.status}
                  </Badge>
                }
                density="compact"
              >
                <TechnicalListItem
                  label="Key prefix"
                  description={key.key_prefix}
                />
                <p className="mt-ui-xs text-system-label text-muted-foreground">
                  Expires: {date(key.expires_at, true)} · Last used:{' '}
                  {date(key.last_used_at)}
                </p>
                <p className="mt-ui-xs break-all font-mono text-system-label">
                  Workspace: {key.permissions.join(', ') || 'No permissions'}
                </p>
                {key.project_grants.map((grant) => (
                  <p
                    key={grant.project_id}
                    className="mt-ui-xs break-all font-mono text-system-label"
                  >
                    {projects.find((project) => project.id === grant.project_id)
                      ?.name ?? grant.project_id}
                    : {grant.permissions.join(', ')}
                  </p>
                ))}
                {key.on_project_create_permissions.length ? (
                  <p className="mt-ui-xs break-all font-mono text-system-label">
                    New Projects: {key.on_project_create_permissions.join(', ')}
                  </p>
                ) : null}
                <div className="mt-ui-sm flex justify-end gap-ui-sm">
                  {active && permissions.includes('keys:rotate') ? (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={pending || Boolean(action)}
                      onClick={() => {
                        setAction({ kind: 'rotate', key })
                        setError(null)
                      }}
                    >
                      Rotate {key.name}
                    </Button>
                  ) : null}
                  {key.status === 'active' &&
                  permissions.includes('keys:revoke') ? (
                    <Button
                      size="sm"
                      variant="destructive"
                      disabled={pending || Boolean(action)}
                      onClick={() => {
                        setAction({ kind: 'revoke', key })
                        setError(null)
                      }}
                    >
                      Revoke {key.name}
                    </Button>
                  ) : null}
                </div>
              </SectionBlock>
            )
          })}
        </div>
      )}
    </div>
  )
}
