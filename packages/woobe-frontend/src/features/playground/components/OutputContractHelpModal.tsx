import { Dialog } from '@/components/ui/Dialog'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'

interface OutputContractHelpModalProps {
  open: boolean
  onClose: () => void
}

const validContract = { message: 'string', confidence: 'float' }
const validOutput = { message: 'ok', confidence: 0.87 }
const invalidOutput = { message: 'ok', confidence: 'number' }
const parsedOutputExample = { answer: '{"message":"ok","confidence":0.87}', parsed_output: { message: 'ok', confidence: 0.87 }, output_parse_error: null }
const invalidParsedOutputExample = { answer: '{"message":"ok","confidence":"number"}', parsed_output: { message: 'ok', confidence: 'number' }, output_parse_error: 'Output validation failed: $.confidence expected number, received string' }
const typeAliases = { string: ['string', 'str', 'text'], number: ['number', 'float', 'double', 'decimal'], integer: ['integer', 'int'], boolean: ['boolean', 'bool'], object: ['object', 'dict'], array: ['array', 'list'] }

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="rounded-container border border-border bg-background/25 p-3"><h3 className="font-mono text-[9px] font-bold text-slate-50">{title}</h3><div className="mt-2 space-y-2 font-sans text-[9px] leading-4 text-muted-foreground">{children}</div></section>
}

export function OutputContractHelpModal({ open, onClose }: OutputContractHelpModalProps) {
  return <Dialog open={open} onClose={onClose} title="Output Contract Help" className="flex h-[min(760px,calc(100svh-2rem))] max-w-3xl flex-col overflow-hidden" contentClassName="min-h-0 flex-1 p-0">
    <div className="scrollbar-thin h-full overflow-y-auto p-4">
      <p className="mb-4 font-sans text-[9px] leading-4 text-muted-foreground">Understand how output contracts, parsed JSON and validation work.</p>
      <div className="space-y-3">
        <Section title="What the output contract is">
          <p>The output contract defines the JSON shape the model is expected to return. It is a runtime agreement between your Agent and downstream code: fields, types and validation rules.</p>
          <p>When JSON output is enabled, the runtime asks the model for valid JSON, parses the final answer and validates the parsed object against this contract.</p>
        </Section>

        <section className="grid gap-3 md:grid-cols-3">
          <div className="rounded-container border border-border bg-background/25 p-3"><p className="mb-2 font-mono text-[8px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">Contract</p><JsonCodeBlock value={validContract} maxHeight={220} actions={['copy', 'format']} /></div>
          <div className="rounded-container border border-emerald-500/20 bg-background/25 p-3"><p className="mb-2 font-mono text-[8px] font-semibold uppercase tracking-[0.1em] text-emerald-300">Valid output</p><JsonCodeBlock value={validOutput} maxHeight={220} actions={['copy', 'format']} /></div>
          <div className="rounded-container border border-red-500/20 bg-background/25 p-3"><p className="mb-2 font-mono text-[8px] font-semibold uppercase tracking-[0.1em] text-red-300">Invalid output</p><JsonCodeBlock value={invalidOutput} maxHeight={220} actions={['copy', 'format']} /></div>
        </section>

        <Section title="Type names are declarations, not literal values">
          <p>Values like <code>"string"</code>, <code>"number"</code> and <code>"float"</code> declare expected types. The model must return a value of that type rather than the declaration word.</p>
          <div className="divide-y divide-border/60 rounded-container border border-border bg-control/25 font-sans text-[9px]">
            <p className="p-2.5"><code>"message": "string"</code> means text such as <code>"ok"</code>.</p>
            <p className="p-2.5"><code>"confidence": "float"</code> means a JSON number such as <code>0.87</code>.</p>
            <p className="p-2.5"><code>"confidence": "number"</code> in final output is invalid because it is a string.</p>
          </div>
        </Section>

        <Section title="Supported type declarations"><p>The contract accepts direct type names and aliases that are normalized before validation.</p><JsonCodeBlock value={typeAliases} maxHeight={320} actions={['copy', 'format']} /></Section>
        <Section title="Strict validation"><p>Strict validation is always active when JSON output is enabled. Invalid JSON or an incompatible response fails the request instead of passing an unreliable shape downstream.</p></Section>
        <Section title="answer, parsed_output and output_parse_error">
          <p><code>answer</code> is the raw model text. <code>parsed_output</code> is the parsed JSON object. <code>output_parse_error</code> describes parsing or validation failures.</p>
          <div className="grid gap-3 md:grid-cols-2"><div className="rounded-container border border-emerald-500/20 bg-background/25 p-3"><p className="mb-2 font-mono text-[8px] font-semibold text-emerald-300">Successful parse</p><JsonCodeBlock value={parsedOutputExample} maxHeight={320} actions={['copy', 'format']} /></div><div className="rounded-container border border-amber-500/20 bg-background/25 p-3"><p className="mb-2 font-mono text-[8px] font-semibold text-amber-300">Validation failure</p><JsonCodeBlock value={invalidParsedOutputExample} maxHeight={320} actions={['copy', 'format']} /></div></div>
        </Section>
      </div>
    </div>
  </Dialog>
}
