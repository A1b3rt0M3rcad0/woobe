import { useState, useEffect } from 'react'
import { useUpdateAgent } from '@/features/agents/hooks'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Select } from '@/components/ui/Select'
import { Separator } from '@/components/ui/Separator'
import { toast } from 'sonner'
import type { Agent } from '@/features/agents/types'

interface AgentQuickSettingsProps {
  agent: Agent
}

const sessionModes = [
  { value: 'stateless', label: 'Stateless' },
  { value: 'stateful', label: 'Stateful' },
]

const statusOptions = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
]

const DEFAULT_SCHEMA = `{
  "type": "object",
  "properties": {
    "category": {
      "type": "string",
      "enum": ["support", "sales", "bug", "other"]
    },
    "summary": {
      "type": "string"
    },
    "confidence": {
      "type": "number"
    }
  },
  "required": ["category", "summary"]
}`

function getResponseFormat(agent: Agent) {
  const settings = agent.settings || {}
  return (settings as Record<string, unknown>).response_format as Record<string, unknown> | undefined
}

function encodeResponseFormat(enabled: boolean, schema: string, strict: boolean): Record<string, unknown> | undefined {
  if (!enabled) return { enabled: false, type: 'text', schema: null, strict: false }
  try {
    return { enabled: true, type: 'json', schema: JSON.parse(schema), strict }
  } catch {
    return undefined
  }
}

export function AgentQuickSettings({ agent }: AgentQuickSettingsProps) {
  const updateAgent = useUpdateAgent(agent.id)
  const currentRf = getResponseFormat(agent)

  const [name, setName] = useState(agent.name)
  const [description, setDescription] = useState(agent.description || '')
  const [systemPrompt, setSystemPrompt] = useState(agent.system_prompt || '')
  const [sessionMode, setSessionMode] = useState(agent.session_mode || 'stateful')
  const [status, setStatus] = useState(agent.status)

  const [jsonEnabled, setJsonEnabled] = useState(
    Boolean(currentRf?.enabled && currentRf?.type === 'json'),
  )
  const [jsonSchema, setJsonSchema] = useState(
    currentRf?.schema ? JSON.stringify(currentRf.schema, null, 2) : DEFAULT_SCHEMA,
  )
  const [jsonStrict, setJsonStrict] = useState(Boolean(currentRf?.strict))
  const [jsonSchemaError, setJsonSchemaError] = useState<string | null>(null)

  useEffect(() => {
    setName(agent.name)
    setDescription(agent.description || '')
    setSystemPrompt(agent.system_prompt || '')
    setSessionMode(agent.session_mode || 'stateful')
    setStatus(agent.status)

    const rf = getResponseFormat(agent)
    setJsonEnabled(Boolean(rf?.enabled && rf?.type === 'json'))
    setJsonSchema(rf?.schema ? JSON.stringify(rf.schema, null, 2) : DEFAULT_SCHEMA)
    setJsonStrict(Boolean(rf?.strict))
    setJsonSchemaError(null)
  }, [agent])

  const rfChanged = () => {
    const rf = getResponseFormat(agent)
    return (
      jsonEnabled !== Boolean(rf?.enabled && rf?.type === 'json') ||
      jsonSchema !== (rf?.schema ? JSON.stringify(rf.schema, null, 2) : DEFAULT_SCHEMA) ||
      jsonStrict !== Boolean(rf?.strict)
    )
  }

  const hasChanges =
    name !== agent.name ||
    description !== (agent.description || '') ||
    systemPrompt !== (agent.system_prompt || '') ||
    sessionMode !== (agent.session_mode || 'stateful') ||
    status !== agent.status ||
    rfChanged()

  const validateSchema = (value: string): boolean => {
    if (!jsonEnabled) return true
    if (!value.trim()) {
      setJsonSchemaError('JSON schema is required when JSON output is enabled.')
      return false
    }
    try {
      JSON.parse(value)
      setJsonSchemaError(null)
      return true
    } catch {
      setJsonSchemaError('Invalid JSON. Please check the syntax.')
      return false
    }
  }

  const handleSave = async () => {
    if (!validateSchema(jsonSchema)) return

    const payload: Record<string, unknown> = {
      name,
      description,
      system_prompt: systemPrompt,
      session_mode: sessionMode,
      status,
    }

    const settings = { ...(agent.settings || {}) }
    const responseFormat = encodeResponseFormat(jsonEnabled, jsonSchema, jsonStrict)
    if (responseFormat) {
      settings.response_format = responseFormat
    } else {
      delete settings.response_format
    }
    payload.settings = settings

    try {
      await updateAgent.mutateAsync(payload as any)
      toast.success('Agent updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update agent')
    }
  }

  const handleReset = () => {
    setName(agent.name)
    setDescription(agent.description || '')
    setSystemPrompt(agent.system_prompt || '')
    setSessionMode(agent.session_mode || 'stateful')
    setStatus(agent.status)

    const rf = getResponseFormat(agent)
    setJsonEnabled(Boolean(rf?.enabled && rf?.type === 'json'))
    setJsonSchema(rf?.schema ? JSON.stringify(rf.schema, null, 2) : DEFAULT_SCHEMA)
    setJsonStrict(Boolean(rf?.strict))
    setJsonSchemaError(null)
  }

  return (
    <Card>
      <CardContent className="p-4 space-y-4">
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Name</label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Description</label>
          <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" />
        </div>
        <div>
          <label className="block text-sm font-medium text-muted mb-1">System Prompt</label>
          <Textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            className="min-h-[120px] font-mono text-sm"
            placeholder="You are a helpful AI assistant..."
          />
        </div>

        <Separator />
        <p className="text-xs font-semibold text-muted">Expected JSON Output</p>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="json-enabled"
            checked={jsonEnabled}
            onChange={(e) => {
              setJsonEnabled(e.target.checked)
              if (!e.target.checked) setJsonSchemaError(null)
            }}
            className="h-4 w-4 rounded border-border bg-background"
          />
          <label htmlFor="json-enabled" className="text-sm font-medium text-muted">
            Enable JSON output
          </label>
        </div>

        <div>
          <label className="block text-sm font-medium text-muted mb-1">JSON Schema</label>
          <Textarea
            value={jsonSchema}
            onChange={(e) => {
              setJsonSchema(e.target.value)
              if (jsonSchemaError) validateSchema(e.target.value)
            }}
            className="min-h-[150px] font-mono text-xs"
            placeholder='{ "type": "object", ... }'
            disabled={!jsonEnabled}
          />
          {jsonSchemaError && (
            <p className="text-xs text-red-400 mt-1">{jsonSchemaError}</p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="json-strict"
            checked={jsonStrict}
            onChange={(e) => setJsonStrict(e.target.checked)}
            disabled={!jsonEnabled}
            className="h-4 w-4 rounded border-border bg-background"
          />
          <label htmlFor="json-strict" className="text-sm font-medium text-muted">
            Strict mode
          </label>
        </div>

        <div className="flex gap-2 pt-1">
          <Button size="sm" onClick={handleSave} disabled={!hasChanges || !!jsonSchemaError} loading={updateAgent.isPending}>
            Save Changes
          </Button>
          <Button size="sm" variant="outline" onClick={handleReset} disabled={!hasChanges}>
            Reset
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
