import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/Textarea'
import { useAgentEditor } from '../AgentEditorContext'

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

function schemaToString(schema: unknown): string {
  if (typeof schema === 'string') return schema
  if (schema && typeof schema === 'object') return JSON.stringify(schema, null, 2)
  return DEFAULT_SCHEMA
}

export function OutputSettingsTab() {
  const { state, setField } = useAgentEditor()
  const { responseFormat } = state

  const handleToggle = (enabled: boolean) => {
    setField('responseFormat', {
      ...responseFormat,
      enabled,
      type: enabled ? 'json' : 'text',
    })
  }

  const handleStrictToggle = (strict: boolean) => {
    setField('responseFormat', { ...responseFormat, strict })
  }

  const handleSchemaChange = (value: string) => {
    setField('responseFormat', { ...responseFormat, schema: value })
  }

  const validateSchema = () => {
    if (!responseFormat.enabled) return true
    const raw = responseFormat.schema as string | null
    if (!raw || !raw.trim()) return false
    try {
      JSON.parse(raw as string)
      return true
    } catch {
      return false
    }
  }

  const previewExample = responseFormat.enabled
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
              checked={responseFormat.enabled}
              onChange={(e) => handleToggle(e.target.checked)}
              className="h-4 w-4 rounded border-border bg-background"
            />
            <label htmlFor="json-enabled" className="text-sm font-medium text-muted">
              Enable JSON output
            </label>
          </div>
          <div>
            <label className="block text-xs font-medium text-muted mb-1">JSON Schema</label>
            <Textarea
              value={schemaToString(responseFormat.schema)}
              onChange={(e) => handleSchemaChange(e.target.value)}
              className="min-h-[180px] font-mono text-xs leading-relaxed"
              placeholder='{ "type": "object", ... }'
              disabled={!responseFormat.enabled}
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="json-strict"
              checked={responseFormat.strict}
              onChange={(e) => handleStrictToggle(e.target.checked)}
              disabled={!responseFormat.enabled}
              className="h-4 w-4 rounded border-border bg-background"
            />
            <label htmlFor="json-strict" className="text-sm font-medium text-muted">
              Strict mode
            </label>
          </div>
          {responseFormat.enabled && (
            <Button size="sm" variant="outline" onClick={() => validateSchema()}>
              Validate Schema
            </Button>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider">API Response Preview</p>
          <pre className="rounded-lg border border-border bg-background p-3 text-xs overflow-x-auto text-muted">
            {JSON.stringify(previewExample, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  )
}
