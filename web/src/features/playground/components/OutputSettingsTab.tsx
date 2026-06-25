import { useMemo } from 'react'
import { JsonEditor } from '@/components/ui/JsonEditor'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { useAgentEditor } from '../AgentEditorContext'

const DEFAULT_SCHEMA = `{
  "message": "string",
  "confidence": "float"
}`

const EXAMPLE_STRUCTURED_OUTPUT = {
  message: 'ok',
  confidence: 0.87,
}

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

  const previewExample = useMemo(() => {
    if (!responseFormat.enabled) {
      return {
        success: true,
        data: {
          answer: 'Hello! How can I help you?',
          session_id: 'uuid',
          message_id: 'uuid',
          usage: {
            input_tokens: 42,
            output_tokens: 17,
            total_tokens: 59,
            cost_usd: 0.0003,
          },
          sources: [],
          tool_calls: [],
          trace_id: 'uuid',
          model: 'gpt-4o-mini',
          provider: 'openai',
          fallback_used: false,
          latency_ms: 843,
          parsed_output: null,
          output_parse_error: null,
        },
      }
    }

    return {
      success: true,
      data: {
        answer: JSON.stringify(EXAMPLE_STRUCTURED_OUTPUT),
        session_id: 'uuid',
        message_id: 'uuid',
        usage: {
          input_tokens: 58,
          output_tokens: 22,
          total_tokens: 80,
          cost_usd: 0.0005,
        },
        sources: [],
        tool_calls: [],
        trace_id: 'uuid',
        model: 'gpt-4o-mini',
        provider: 'openai',
        fallback_used: false,
        latency_ms: 1024,
        parsed_output: EXAMPLE_STRUCTURED_OUTPUT,
        output_parse_error: null,
      },
    }
  }, [responseFormat.enabled])

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
            <label className="block text-xs font-medium text-muted mb-1">Output contract</label>
            <JsonEditor
              value={schemaToString(responseFormat.schema)}
              onChange={handleSchemaChange}
              editable
              disabled={!responseFormat.enabled}
              actions={['format', 'validate', 'clear']}
              minHeight={180}
              placeholder='{ "message": "string" }'
            />
            <p className="mt-2 text-[11px] leading-relaxed text-muted">
              Contract values such as <code>"string"</code>, <code>"number"</code> and <code>"float"</code> are type declarations.
              The model output must return real values, for example <code>{'{ "confidence": 0.87 }'}</code>, not <code>{'{ "confidence": "number" }'}</code>.
            </p>
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
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider">API Response Preview</p>
          <JsonCodeBlock
            value={previewExample}
            title="Preview"
            maxHeight={480}
            actions={['copy', 'format', 'expand']}
          />
        </div>
      </div>
    </div>
  )
}
