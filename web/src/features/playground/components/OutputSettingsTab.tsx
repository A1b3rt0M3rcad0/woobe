import { useState, useEffect } from 'react'
import { useUpdateAgent } from '@/features/agents/hooks'
import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/Textarea'
import { Separator } from '@/components/ui/Separator'
import { Badge } from '@/components/ui/Badge'
import { toast } from 'sonner'
import type { Agent } from '@/features/agents/types'

interface OutputSettingsTabProps {
  agent: Agent
}

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

export function OutputSettingsTab({ agent }: OutputSettingsTabProps) {
  const updateAgent = useUpdateAgent(agent.id)
  const currentRf = getResponseFormat(agent)

  const [jsonEnabled, setJsonEnabled] = useState(
    Boolean(currentRf?.enabled && currentRf?.type === 'json'),
  )
  const [jsonSchema, setJsonSchema] = useState(
    currentRf?.schema ? JSON.stringify(currentRf.schema, null, 2) : DEFAULT_SCHEMA,
  )
  const [jsonStrict, setJsonStrict] = useState(Boolean(currentRf?.strict))
  const [jsonSchemaError, setJsonSchemaError] = useState<string | null>(null)

  useEffect(() => {
    const rf = getResponseFormat(agent)
    setJsonEnabled(Boolean(rf?.enabled && rf?.type === 'json'))
    setJsonSchema(rf?.schema ? JSON.stringify(rf.schema, null, 2) : DEFAULT_SCHEMA)
    setJsonStrict(Boolean(rf?.strict))
    setJsonSchemaError(null)
  }, [agent])

  const hasChanges = () => {
    const rf = getResponseFormat(agent)
    return (
      jsonEnabled !== Boolean(rf?.enabled && rf?.type === 'json') ||
      jsonSchema !== (rf?.schema ? JSON.stringify(rf.schema, null, 2) : DEFAULT_SCHEMA) ||
      jsonStrict !== Boolean(rf?.strict)
    )
  }

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

    const settings = { ...(agent.settings || {}) }
    const responseFormat = encodeResponseFormat(jsonEnabled, jsonSchema, jsonStrict)
    if (responseFormat) {
      settings.response_format = responseFormat
    } else {
      delete settings.response_format
    }

    try {
      await updateAgent.mutateAsync({ settings } as any)
      toast.success('Output settings updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update output settings')
    }
  }

  const handleReset = () => {
    const rf = getResponseFormat(agent)
    setJsonEnabled(Boolean(rf?.enabled && rf?.type === 'json'))
    setJsonSchema(rf?.schema ? JSON.stringify(rf.schema, null, 2) : DEFAULT_SCHEMA)
    setJsonStrict(Boolean(rf?.strict))
    setJsonSchemaError(null)
  }

  const previewExample = jsonEnabled
    ? {
        success: true,
        data: {
          answer: '{"message":"Response in JSON format","confidence":0.92}',
          parsed_output: {
            message: 'Response in JSON format',
            confidence: 0.92,
          },
          output_parse_error: null,
        },
      }
    : {
        success: true,
        data: {
          answer: 'Hello! How can I help you?',
          parsed_output: null,
          output_parse_error: null,
        },
      }

  return (
    <div className="p-4 space-y-4">
      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider">JSON Output</p>
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
            <label className="block text-xs font-medium text-muted mb-1">JSON Schema</label>
            <Textarea
              value={jsonSchema}
              onChange={(e) => {
                setJsonSchema(e.target.value)
                if (jsonSchemaError) validateSchema(e.target.value)
              }}
              className="min-h-[180px] font-mono text-xs leading-relaxed"
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
          {jsonEnabled && (
            <Button size="sm" variant="outline" onClick={() => validateSchema(jsonSchema)}>
              Validate Schema
            </Button>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <div className="flex items-center gap-2">
            <p className="text-xs font-semibold text-muted uppercase tracking-wider">API Response Preview</p>
            {jsonEnabled && <Badge variant="success" className="text-[10px]">JSON</Badge>}
          </div>
          <pre className="rounded-lg border border-border bg-background p-3 text-xs overflow-x-auto text-muted">
            {JSON.stringify(previewExample, null, 2)}
          </pre>
        </div>
      </div>

      {hasChanges() && (
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={handleReset}>
            Reset
          </Button>
          <Button size="sm" onClick={handleSave} disabled={!!jsonSchemaError} loading={updateAgent.isPending}>
            Save Changes
          </Button>
        </div>
      )}
    </div>
  )
}
