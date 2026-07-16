import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { ScrollArea } from '@/components/ui/ScrollArea'

interface OutputContractHelpModalProps {
  open: boolean
  onClose: () => void
}

const validContract = {
  message: 'string',
  confidence: 'float',
}

const validOutput = {
  message: 'ok',
  confidence: 0.87,
}

const invalidOutput = {
  message: 'ok',
  confidence: 'number',
}

const parsedOutputExample = {
  answer: '{"message":"ok","confidence":0.87}',
  parsed_output: {
    message: 'ok',
    confidence: 0.87,
  },
  output_parse_error: null,
}

const invalidParsedOutputExample = {
  answer: '{"message":"ok","confidence":"number"}',
  parsed_output: {
    message: 'ok',
    confidence: 'number',
  },
  output_parse_error: 'Output validation failed: $.confidence expected number, received string',
}

const typeAliases = {
  string: ['string', 'str', 'text'],
  number: ['number', 'float', 'double', 'decimal'],
  integer: ['integer', 'int'],
  boolean: ['boolean', 'bool'],
  object: ['object', 'dict'],
  array: ['array', 'list'],
}

export function OutputContractHelpModal({ open, onClose }: OutputContractHelpModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-start justify-center pt-12 bg-black/60 backdrop-blur-sm"
      onClick={(event) => { if (event.target === overlayRef.current) onClose() }}
    >
      <ScrollArea className="w-full max-w-3xl max-h-[84vh] rounded-xl border border-border bg-surface shadow-xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-surface p-4">
          <div>
            <h2 className="text-sm font-semibold text-white">Output Contract Help</h2>
            <p className="mt-0.5 text-[11px] text-muted">
              Understand how output contracts, parsed JSON and validation work.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-muted hover:text-white hover:bg-accent transition-colors"
            aria-label="Close output help"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 space-y-5">
          <section className="rounded-lg border border-border bg-background p-4 space-y-3">
            <h3 className="text-sm font-semibold text-white">What the output contract is</h3>
            <p className="text-xs leading-relaxed text-muted">
              The output contract defines the JSON shape the model is expected to return. It is not the final answer itself.
              It is a runtime agreement between your agent and the rest of your application: fields, types and validation rules.
            </p>
            <p className="text-xs leading-relaxed text-muted">
              When JSON output is enabled, the runtime asks the model to answer with valid JSON, parses the final answer,
              and then validates the parsed object against this contract.
            </p>
          </section>

          <section className="grid gap-3 md:grid-cols-3">
            <div className="rounded-lg border border-border bg-background p-3 space-y-2">
              <p className="text-xs font-semibold text-muted uppercase tracking-wider">Contract</p>
              <JsonCodeBlock value={validContract} maxHeight={220} actions={['copy', 'format']} />
            </div>
            <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-3 space-y-2">
              <p className="text-xs font-semibold text-green-300 uppercase tracking-wider">Valid output</p>
              <JsonCodeBlock value={validOutput} maxHeight={220} actions={['copy', 'format']} />
            </div>
            <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 space-y-2">
              <p className="text-xs font-semibold text-red-300 uppercase tracking-wider">Invalid output</p>
              <JsonCodeBlock value={invalidOutput} maxHeight={220} actions={['copy', 'format']} />
            </div>
          </section>

          <section className="rounded-lg border border-border bg-background p-4 space-y-3">
            <h3 className="text-sm font-semibold text-white">Type names are declarations, not literal values</h3>
            <p className="text-xs leading-relaxed text-muted">
              Values like <code>"string"</code>, <code>"number"</code> and <code>"float"</code> declare expected types.
              They tell the runtime what kind of value the model must return. The model must not literally return those words.
            </p>
            <div className="rounded-md border border-border bg-surface p-3 text-xs leading-relaxed text-muted space-y-2">
              <p><code>"message": "string"</code> means the model must return text, such as <code>"ok"</code>.</p>
              <p><code>"confidence": "float"</code> means the model must return a JSON number, such as <code>0.87</code>.</p>
              <p><code>"confidence": "number"</code> in the final model output is invalid because it is a string, not a number.</p>
            </div>
          </section>

          <section className="rounded-lg border border-border bg-background p-4 space-y-3">
            <h3 className="text-sm font-semibold text-white">Supported type declarations</h3>
            <p className="text-xs leading-relaxed text-muted">
              The contract accepts direct type names and a few aliases. Aliases are normalized before validation.
            </p>
            <JsonCodeBlock value={typeAliases} maxHeight={320} actions={['copy', 'format']} />
          </section>

          <section className="rounded-lg border border-border bg-background p-4 space-y-3">
            <h3 className="text-sm font-semibold text-white">Strict validation</h3>
            <p className="text-xs leading-relaxed text-muted">
              Strict validation is always active when JSON output is enabled. Invalid JSON or a response that does not match the output contract fails the request, preventing downstream code from receiving an unreliable JSON shape.
            </p>
          </section>

          <section className="rounded-lg border border-border bg-background p-4 space-y-3">
            <h3 className="text-sm font-semibold text-white">answer, parsed_output and output_parse_error</h3>
            <p className="text-xs leading-relaxed text-muted">
              <code>answer</code> is the raw text returned by the model. <code>parsed_output</code> is the JSON object parsed from that answer.
              <code>output_parse_error</code> explains parsing or validation failures.
            </p>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-md border border-green-500/30 bg-green-500/5 p-3 space-y-2">
                <p className="text-xs font-semibold text-green-300">Successful parse</p>
                <JsonCodeBlock value={parsedOutputExample} maxHeight={320} actions={['copy', 'format']} />
              </div>
              <div className="rounded-md border border-yellow-500/30 bg-yellow-500/5 p-3 space-y-2">
                <p className="text-xs font-semibold text-yellow-300">Validation failure</p>
                <JsonCodeBlock value={invalidParsedOutputExample} maxHeight={320} actions={['copy', 'format']} />
              </div>
            </div>
          </section>
        </div>
      </ScrollArea>
    </div>
  )
}
