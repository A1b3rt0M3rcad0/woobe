import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound } from 'lucide-react'
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
  TechnicalListItem,
} from '@woobe/ui'
import { CopyButton } from '@/components/common/CopyButton'
import { API_BASE_URL } from '@/lib/api/client'
import type { Project } from '@/features/projects/types'
import {
  createControlKey,
  getEffectiveAccess,
  getPermissionCatalog,
  listControlKeys,
  revokeControlKey,
  rotateControlKey,
  type ControlKey,
  type IssuedControlKey,
  type ProjectGrant,
} from './api'

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
  return (
    <details className="rounded-panel border border-border p-ui-sm">
      <summary className="cursor-pointer text-system-control font-medium">
        {title} ({selected.length} selected)
      </summary>
      <div className="mt-ui-sm grid gap-ui-xs sm:grid-cols-2">
        {permissions.map((permission) => (
          <label
            key={permission}
            className="flex items-center gap-ui-sm text-system-label"
          >
            <Checkbox
              checked={selected.includes(permission)}
              onChange={() =>
                onChange(
                  selected.includes(permission)
                    ? selected.filter((value) => value !== permission)
                    : [...selected, permission],
                )
              }
            />
            <span className="font-mono">{permission}</span>
          </label>
        ))}
      </div>
      <div className="mt-ui-sm flex gap-ui-xs">
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
        <Button size="sm" variant="outline" onClick={() => onChange(permissions)}>
          All available permissions
        </Button>
        <Button size="sm" variant="outline" onClick={() => onChange([])}>
          Clear
        </Button>
      </div>
    </details>
  )
}

function ProjectPermissions({
  workspaceId,
  project,
  catalog,
  grant,
  onChange,
}: {
  workspaceId: string
  project: Project
  catalog: string[]
  grant?: ProjectGrant
  onChange: (grant: ProjectGrant) => void
}) {
  const access = useQuery({
    queryKey: ['effective-access', workspaceId, project.id],
    queryFn: () => getEffectiveAccess(workspaceId, project.id),
    retry: false,
  })
  if (access.isPending)
    return (
      <p className="text-system-label text-muted-foreground">
        Loading permissions for {project.name}…
      </p>
    )
  if (access.isError)
    return (
      <p role="alert" className="text-system-label text-muted-foreground">
        Unable to load delegable permissions for {project.name}.
      </p>
    )
  const permissions = catalog.filter((permission) =>
    access.data.permissions.includes(permission),
  )
  return (
    <div className="grid gap-ui-xs">
      <PermissionChoices
        title={project.name}
        permissions={permissions}
        selected={grant?.permissions ?? []}
        onChange={(selected) =>
          onChange({
            project_id: project.id,
            permissions: selected,
            conditions: access.data.conditions,
          })
        }
      />
      {Object.keys(access.data.conditions).length > 0 ? (
        <p className="text-system-label text-muted-foreground">
          Your existing access restrictions will also apply to this grant.
        </p>
      ) : null}
    </div>
  )
}

function date(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Never'
}

export function WorkspaceCliKeys({
  workspaceId,
  projects,
}: {
  workspaceId: string
  projects: Project[]
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
  const [expiration, setExpiration] = useState('')
  const [workspacePermissions, setWorkspacePermissions] = useState<string[]>([])
  const [creationPermissions, setCreationPermissions] = useState<string[]>([])
  const [grants, setGrants] = useState<ProjectGrant[]>([])
  const [issued, setIssued] = useState<IssuedControlKey | null>(null)
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
    if (pending || !name.trim() || !catalog.data) return
    setPending(true)
    setError(null)
    try {
      const body = {
        name: name.trim(),
        description: description.trim() || null,
        expires_at: expiration ? new Date(expiration).toISOString() : null,
        permissions: workspacePermissions,
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
        setExpiration('')
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
          description="Run the import command by itself, paste the key into stdin, then press Enter and Ctrl+D on POSIX. The secret is never passed as a command-line argument."
        >
          <CodePanel
            title="Import credential"
            actions={
              <CopyButton text="woobe auth credential import --name workspace-cli --stdin" />
            }
          >
            <code className="block p-ui-md font-mono text-system-label">
              woobe auth credential import --name workspace-cli --stdin
            </code>
          </CodePanel>
          <CodePanel
            title="CLI setup"
            actions={
              <CopyButton
                text={`woobe context create woobe --api-url ${API_BASE_URL}\nwoobe context credential attach woobe --credential workspace-cli\nwoobe context use woobe\nwoobe context set --workspace ${workspaceId}`}
              />
            }
          >
            <pre className="overflow-x-auto p-ui-md font-mono text-system-label">{`woobe context create woobe --api-url ${API_BASE_URL}\nwoobe context credential attach woobe --credential workspace-cli\nwoobe context use woobe\nwoobe context set --workspace ${workspaceId}`}</pre>
          </CodePanel>
          <p className="mt-ui-sm text-system-label text-muted-foreground">
            Select a granted Project with{' '}
            <code>woobe context set --project PROJECT_ID</code>. Runtime
            execution uses a separate Runtime Key.
          </p>
        </SectionBlock>
        <div className="flex justify-end">
          <Button onClick={() => setIssued(null)}>I saved the key</Button>
        </div>
      </div>
    )

  return (
    <div className="grid gap-ui-md">
      <SectionBlock
        title="CLI Keys"
        description="Control Keys authenticate woobe-cli and automation. Choose Workspace permissions and separate grants for each Project. Runtime Keys in Project settings are for Agent and Network execution."
        actions={
          !creating && permissions.includes('keys:create') ? (
            <Button
              onClick={() => {
                setCreating(true)
                setError(null)
              }}
            >
              Create CLI key
            </Button>
          ) : undefined
        }
      />
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>CLI key operation failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {creating ? (
        <SectionBlock
          title="Create CLI key"
          description="Only the selected permissions are granted. No permissions are selected by default."
        >
          <div className="grid gap-ui-md">
            <Field>
              <FieldLabel htmlFor="cli-key-name">Name</FieldLabel>
              <Input
                id="cli-key-name"
                value={name}
                maxLength={255}
                onChange={(event) => setName(event.target.value)}
                placeholder="My workstation"
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="cli-key-description">
                Description (optional)
              </FieldLabel>
              <Input
                id="cli-key-description"
                value={description}
                maxLength={500}
                onChange={(event) => setDescription(event.target.value)}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="cli-key-expiration">
                Expiration (optional)
              </FieldLabel>
              <Input
                id="cli-key-expiration"
                type="datetime-local"
                value={expiration}
                onChange={(event) => setExpiration(event.target.value)}
              />
              <p className="text-system-label text-muted-foreground">
                Leave blank for no expiration.
              </p>
            </Field>
            {catalog.isError ? (
              <Alert variant="destructive">
                <AlertTitle>Unable to load permission catalog</AlertTitle>
                <Button
                  variant="outline"
                  onClick={() => void catalog.refetch()}
                >
                  Retry
                </Button>
              </Alert>
            ) : catalog.data ? (
              <>
                <PermissionChoices
                  title="Workspace permissions"
                  permissions={catalog.data.permissions.workspace.filter(
                    (permission) => permissions.includes(permission),
                  )}
                  selected={workspacePermissions}
                  onChange={setWorkspacePermissions}
                />
                <SectionBlock
                  title="Project grants"
                  description="Permissions apply only to the Projects selected below."
                  density="compact"
                >
                  <div className="grid gap-ui-xs">
                    {projects.map((project) => (
                      <ProjectPermissions
                        key={project.id}
                        workspaceId={workspaceId}
                        project={project}
                        catalog={catalog.data!.permissions.project}
                        grant={grants.find(
                          (grant) => grant.project_id === project.id,
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
                    ))}
                  </div>
                  {!projects.length ? (
                    <p className="text-system-label text-muted-foreground">
                      No Projects available. You can grant Workspace permissions
                      now.
                    </p>
                  ) : null}
                </SectionBlock>
                {workspacePermissions.includes('projects:create') ? (
                  <PermissionChoices
                    title="Permissions on newly created Projects"
                    permissions={catalog.data.permissions.project}
                    selected={creationPermissions}
                    onChange={setCreationPermissions}
                  />
                ) : null}
              </>
            ) : (
              <p role="status">Loading permission catalog…</p>
            )}
            <div className="flex justify-end gap-ui-sm">
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
                  Boolean(
                    expiration && new Date(expiration).getTime() <= Date.now(),
                  )
                }
                onClick={() => void submitCreate()}
              >
                Create key
              </Button>
            </div>
          </div>
        </SectionBlock>
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
      {keys.isPending ? (
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
                  Expires: {date(key.expires_at)} · Last used:{' '}
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
