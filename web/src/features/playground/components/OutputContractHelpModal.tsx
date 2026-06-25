import { useEffect, useMemo, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { ScrollArea } from '@/components/ui/ScrollArea'

type HelpSection = 'contract' | 'preview'

interface OutputContractHelpModalProps {
  open: boolean
  onClose: () => void
  initialSection: HelpSection
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

function SectionButton({
  active,
  children,
  onClick,
}: {
  active: boolean
  children: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
        active ? 'border-primary bg-primary/10 text-primary' : 'border-border bg-background text-muted hover:text-white hover:border-primary/40'
      }`}
    >
      {children}
    </button>
  )
}

export function OutputContractHelpModal({ open, onClose, initialSection }: OutputContractHelpModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const [activeSection, setActiveSection] = useState<HelpSection>(initialSection)

  useEffect(() => {
    if (open) setActiveSection(initialSection)
  }, [open, initialSection])

  useEffect(() => {
    if (!open) return
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  const title = useMemo(
    () => activeSection === 'contract' ? 'Output Contract Help' : 'Draft Runtime Preview Help',
    [activeSection],
  )

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
            <h2 className="text-sm font-semibold text-white">{title}</h2>
            <p className="mt-0.5 text-[11px] text-muted">
              Understand how output contracts, parsed JSON and playground draft previews work.
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
          <div className="flex gap-2">
            <SectionButton active={activeSection === 'contract'} onClick={() => setActiveSection('contract')}>
              Output Contract
            </SectionButton>
            <SectionButton active={activeSection === 'preview'} onClick={() => setActiveSection('preview')}>
              Draft Runtime Preview
            </SectionButton>
          </div>

          {activeSection === 'contract' ? (
            <div className="space-y-5">
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
                <h3 className="text-sm font-semibold text-white">Strict mode</h3>
                <p className="text-xs leading-relaxed text-muted">
                  Strict mode controls how the runtime behaves when the model output cannot be parsed or does not match the contract.
                </p>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-md border border-border bg-surface p-3">
                    <p className="text-xs font-semibold text-white">Strict mode ON</p>
                    <p className="mt-1 text-xs leading-relaxed text-muted">
                      Invalid JSON or a type mismatch fails the request. This is useful when downstream code depends on a reliable JSON shape.
                    </p>
                  </div>
                  <div className="rounded-md border border-border bg-surface p-3">
                    <p className="text-xs font-semibold text-white">Strict mode OFF</p>
                    <p className="mt-1 text-xs leading-relaxed text-muted">
                      The request can still complete, but <code>output_parse_error</code> is filled so you can see exactly what failed.
                    </p>
                  </div>
                </div>
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
          ) : (
            <div className="space-y-5">
              <section className="rounded-lg border border-border bg-background p-4 space-y-3">
                <h3 className="text-sm font-semibold text-white">What Draft Runtime Preview shows</h3>
                <p className="text-xs leading-relaxed text-muted">
                  Draft Runtime Preview shows the current playground runtime request context for this agent. It is focused on the draft you are editing,
                  not on the production or staging release contracts.
                </p>
                <p className="text-xs leading-relaxed text-muted">
                  The most important field is <code>snapshot_override</code>. That field contains the current draft configuration that will be sent to the runtime
                  when you execute the agent from the playground.
                </p>
              </section>

              <section className="rounded-lg border border-border bg-background p-4 space-y-3">
                <h3 className="text-sm font-semibold text-white">Why snapshot_override exists</h3>
                <p className="text-xs leading-relaxed text-muted">
                  The playground lets you test unsaved or draft changes without promoting them to staging or production. To do that safely,
                  the frontend sends the base agent ID plus a snapshot of the current draft configuration.
                </p>
                <div className="rounded-md border border-border bg-surface p-3 text-xs leading-relaxed text-muted space-y-2">
                  <p><code>execution_context: "playground"</code> tells the runtime this is an editor/playground execution.</p>
                  <p><code>snapshot_override</code> tells the runtime which draft configuration to use for this execution.</p>
                  <p>This does not mutate the saved production release and does not change the staging release.</p>
                </div>
              </section>

              <section className="rounded-lg border border-border bg-background p-4 space-y-3">
                <h3 className="text-sm font-semibold text-white">What can appear inside the draft snapshot</h3>
                <p className="text-xs leading-relaxed text-muted">
                  The snapshot can include the agent name, description, system prompt, provider, model, credentials, generation settings,
                  response format, output schema, session mode, knowledge references and runtime configuration.
                </p>
                <p className="text-xs leading-relaxed text-muted">
                  If you edit the output contract, provider, model, strict mode or system prompt, the preview should update immediately because it is based on the current editor state.
                </p>
              </section>

              <section className="rounded-lg border border-border bg-background p-4 space-y-3">
                <h3 className="text-sm font-semibold text-white">Draft preview versus API Reference</h3>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-md border border-border bg-surface p-3">
                    <p className="text-xs font-semibold text-white">Draft Runtime Preview</p>
                    <p className="mt-1 text-xs leading-relaxed text-muted">
                      Shows what the playground sends for the current draft using <code>snapshot_override</code>.
                    </p>
                  </div>
                  <div className="rounded-md border border-border bg-surface p-3">
                    <p className="text-xs font-semibold text-white">API Reference</p>
                    <p className="mt-1 text-xs leading-relaxed text-muted">
                      Shows public runtime contracts for <code>production</code> and <code>staging</code>, each based on its active release snapshot.
                    </p>
                  </div>
                </div>
              </section>

              <section className="rounded-lg border border-border bg-background p-4 space-y-3">
                <h3 className="text-sm font-semibold text-white">How output contracts affect the preview</h3>
                <p className="text-xs leading-relaxed text-muted">
                  If JSON output is enabled, the draft preview includes the current <code>response_format</code> and schema inside <code>snapshot_override</code>.
                  Type names such as <code>"string"</code>, <code>"number"</code> and <code>"float"</code> are still declarations. They describe what the model must return later.
                </p>
                <p className="text-xs leading-relaxed text-muted">
                  The preview does not claim the model already returned those values. It only shows the contract that will be sent to the runtime.
                </p>
              </section>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
