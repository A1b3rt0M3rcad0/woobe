import { useEffect, useState } from 'react'
import { KeyRound, Plus, Save, Trash2 } from 'lucide-react'
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Button,
  Field,
  FieldDescription,
  FieldLabel,
  Input,
  SectionBlock,
  Select,
} from '@woobe/ui'
import { toast } from 'sonner'

import {
  useDeleteProjectEnvironmentKey,
  useProjectEnvironmentKeys,
  useUpsertProjectEnvironmentKey,
} from '@/features/projects/hooks'
import type {
  ProjectEnvironment,
  ProjectEnvironmentKey,
  ProjectEnvironmentKind,
} from '@/features/projects/types'

const ENVIRONMENTS: ProjectEnvironment[] = ['draft', 'staging', 'production']

const KIND_OPTIONS = [
  { value: 'value', label: 'Value' },
  { value: 'secret', label: 'Secret' },
]

interface EnvironmentKeyRowProps {
  projectId: string
  item: ProjectEnvironmentKey
}

function EnvironmentKeyRow({ projectId, item }: EnvironmentKeyRowProps) {
  const upsert = useUpsertProjectEnvironmentKey()
  const remove = useDeleteProjectEnvironmentKey()
  const referencedTools = item.used_by_tools || []
  const inUse = referencedTools.length > 0
  const [kind, setKind] = useState<ProjectEnvironmentKind>(item.kind)
  const [values, setValues] = useState<Record<ProjectEnvironment, string>>({
    draft: item.kind === 'value' ? item.values.draft.value || '' : '',
    staging: item.kind === 'value' ? item.values.staging.value || '' : '',
    production: item.kind === 'value' ? item.values.production.value || '' : '',
  })
  const [clear, setClear] = useState<Set<ProjectEnvironment>>(new Set())

  useEffect(() => {
    setKind(item.kind)
    setValues({
      draft: item.kind === 'value' ? item.values.draft.value || '' : '',
      staging: item.kind === 'value' ? item.values.staging.value || '' : '',
      production: item.kind === 'value' ? item.values.production.value || '' : '',
    })
    setClear(new Set())
  }, [item])

  const save = async () => {
    const payloadValues: Partial<Record<ProjectEnvironment, string>> = {}
    for (const environment of ENVIRONMENTS) {
      if (clear.has(environment)) continue
      const value = values[environment]
      if (kind === 'value') {
        if (item.kind === 'secret' && value.length === 0) continue
        payloadValues[environment] = value
      } else if (value.length > 0) {
        payloadValues[environment] = value
      }
    }

    try {
      await upsert.mutateAsync({
        projectId,
        key: item.key,
        data: {
          kind,
          values: payloadValues,
          clear_environments: [...clear],
        },
      })
      toast.success(`${item.key} updated`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update Project Environment key')
    }
  }

  const deleteKey = async () => {
    if (inUse) {
      toast.error(
        `${item.key} is used by ${referencedTools.length} Tool${referencedTools.length === 1 ? '' : 's'}. Edit or delete those Tools first.`,
      )
      return
    }
    try {
      await remove.mutateAsync({ projectId, key: item.key })
      toast.success(`${item.key} deleted`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to delete Project Environment key')
    }
  }

  const toggleClear = (environment: ProjectEnvironment) => {
    setClear((current) => {
      const next = new Set(current)
      if (next.has(environment)) next.delete(environment)
      else next.add(environment)
      return next
    })
  }

  return (
    <div className="grid gap-ui-md rounded-lg border border-border bg-background/30 p-ui-md">
      <div className="flex flex-wrap items-end gap-ui-sm">
        <Field className="min-w-0 flex-1">
          <FieldLabel>Key</FieldLabel>
          <Input value={item.key} readOnly className="font-mono" />
        </Field>
        <Field className="w-36">
          <FieldLabel>Type</FieldLabel>
          <Select
            value={kind}
            options={KIND_OPTIONS}
            onChange={(event) => setKind(event.target.value as ProjectEnvironmentKind)}
          />
        </Field>
        <Button
          type="button"
          size="iconSm"
          variant="ghost"
          onClick={() => void deleteKey()}
          loading={remove.isPending}
          disabled={inUse}
          title={inUse ? 'Edit or delete dependent Tools before removing this key' : undefined}
          aria-label={`Delete ${item.key}`}
        >
          <Trash2 className="h-icon w-icon text-error" />
        </Button>
      </div>

      {inUse ? (
        <Alert>
          <AlertTitle>Used by Tool{referencedTools.length === 1 ? '' : 's'}</AlertTitle>
          <AlertDescription>
            {referencedTools.map((tool) => tool.name).join(', ')}. Edit these Tools to use another
            Project Environment key, or delete the Tools, before removing <span className="font-mono">{item.key}</span>.
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-ui-sm lg:grid-cols-3">
        {ENVIRONMENTS.map((environment) => {
          const state = item.values[environment]
          const clearing = clear.has(environment)
          const secretConfigured = item.kind === 'secret' && state.configured
          return (
            <Field key={environment}>
              <div className="flex items-center justify-between gap-ui-xs">
                <FieldLabel className="capitalize">{environment}</FieldLabel>
                {state.configured ? (
                  <button
                    type="button"
                    className="font-mono text-[10px] text-muted-foreground hover:text-foreground"
                    onClick={() => toggleClear(environment)}
                  >
                    {clearing ? 'keep value' : 'clear'}
                  </button>
                ) : null}
              </div>
              <Input
                type={kind === 'secret' ? 'password' : 'text'}
                value={clearing ? '' : values[environment]}
                disabled={clearing}
                spellCheck={false}
                autoComplete="off"
                onChange={(event) => setValues((current) => ({
                  ...current,
                  [environment]: event.target.value,
                }))}
                placeholder={
                  clearing
                    ? 'Will be cleared'
                    : secretConfigured && kind === 'secret'
                      ? 'Configured — enter to replace'
                      : 'Not configured'
                }
                className="font-mono"
              />
              <FieldDescription>
                {clearing
                  ? 'This environment value will be removed.'
                  : kind === 'secret' && state.configured
                    ? 'Stored value is hidden and preserved while this field stays empty.'
                    : state.configured
                      ? 'Configured for this environment.'
                      : 'No value configured.'}
              </FieldDescription>
            </Field>
          )
        })}
      </div>

      <div className="flex justify-end">
        <Button type="button" size="sm" onClick={() => void save()} loading={upsert.isPending}>
          <Save className="h-icon w-icon" />
          Save key
        </Button>
      </div>
    </div>
  )
}

export function ProjectEnvironmentSettings({ projectId }: { projectId: string }) {
  const query = useProjectEnvironmentKeys(projectId)
  const upsert = useUpsertProjectEnvironmentKey()
  const [adding, setAdding] = useState(false)
  const [keyName, setKeyName] = useState('')
  const [kind, setKind] = useState<ProjectEnvironmentKind>('value')
  const [values, setValues] = useState<Record<ProjectEnvironment, string>>({
    draft: '',
    staging: '',
    production: '',
  })

  const create = async () => {
    const key = keyName.trim()
    if (!key) {
      toast.error('Environment key is required')
      return
    }
    try {
      await upsert.mutateAsync({
        projectId,
        key,
        data: {
          kind,
          values: Object.fromEntries(
            ENVIRONMENTS
              .filter((environment) => values[environment].length > 0)
              .map((environment) => [environment, values[environment]]),
          ),
        },
      })
      setKeyName('')
      setKind('value')
      setValues({ draft: '', staging: '', production: '' })
      setAdding(false)
      toast.success(`${key} created`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create Project Environment key')
    }
  }

  return (
    <SectionBlock
      title="Project Environment"
      description="Project-scoped Tool configuration resolved automatically from the execution environment. Agents never receive these values as Tool inputs."
    >
      {query.isError ? (
        <Alert variant="destructive">
          <AlertTitle>Project Environment unavailable</AlertTitle>
          <AlertDescription>
            {query.error instanceof Error ? query.error.message : 'Unable to load environment keys'}
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-ui-sm">
        {(query.data || []).map((item) => (
          <EnvironmentKeyRow key={item.id} projectId={projectId} item={item} />
        ))}

        {!query.isPending && !query.isError && (query.data || []).length === 0 && !adding ? (
          <div className="rounded-lg border border-dashed border-border p-ui-md text-center">
            <KeyRound className="mx-auto h-icon-lg w-icon-lg text-muted-foreground" />
            <p className="mt-ui-xs font-sans text-product-small text-muted-foreground">
              No Project Environment keys configured.
            </p>
          </div>
        ) : null}

        {adding ? (
          <div className="grid gap-ui-md rounded-lg border border-border bg-background/30 p-ui-md">
            <div className="grid gap-ui-sm sm:grid-cols-[minmax(0,1fr)_9rem]">
              <Field>
                <FieldLabel>Key</FieldLabel>
                <Input
                  value={keyName}
                  onChange={(event) => setKeyName(event.target.value)}
                  placeholder="API_KEY"
                  spellCheck={false}
                  className="font-mono"
                />
                <FieldDescription>Letters, numbers and underscore; must not start with a number.</FieldDescription>
              </Field>
              <Field>
                <FieldLabel>Type</FieldLabel>
                <Select
                  value={kind}
                  options={KIND_OPTIONS}
                  onChange={(event) => setKind(event.target.value as ProjectEnvironmentKind)}
                />
              </Field>
            </div>

            <div className="grid gap-ui-sm lg:grid-cols-3">
              {ENVIRONMENTS.map((environment) => (
                <Field key={environment}>
                  <FieldLabel className="capitalize">{environment}</FieldLabel>
                  <Input
                    type={kind === 'secret' ? 'password' : 'text'}
                    value={values[environment]}
                    spellCheck={false}
                    autoComplete="off"
                    onChange={(event) => setValues((current) => ({
                      ...current,
                      [environment]: event.target.value,
                    }))}
                    placeholder="Optional"
                    className="font-mono"
                  />
                </Field>
              ))}
            </div>

            <div className="flex justify-end gap-ui-sm">
              <Button type="button" size="sm" variant="outline" onClick={() => setAdding(false)}>
                Cancel
              </Button>
              <Button type="button" size="sm" onClick={() => void create()} loading={upsert.isPending}>
                <Save className="h-icon w-icon" />
                Create key
              </Button>
            </div>
          </div>
        ) : (
          <Button type="button" size="sm" variant="outline" onClick={() => setAdding(true)}>
            <Plus className="h-icon w-icon" />
            Add environment key
          </Button>
        )}
      </div>
    </SectionBlock>
  )
}
