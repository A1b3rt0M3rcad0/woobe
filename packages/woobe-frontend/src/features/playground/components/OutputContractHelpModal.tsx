import type { ReactNode } from 'react'
import { Badge, Dialog, SectionBlock, TechnicalListItem, woobeLayout } from '@woobe/ui'
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

function HelpSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <SectionBlock title={title} density="compact">
      <div className="grid gap-ui-sm font-sans text-product-small leading-5 text-muted-foreground">{children}</div>
    </SectionBlock>
  )
}

export function OutputContractHelpModal({ open, onClose }: OutputContractHelpModalProps) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Output Contract Help"
      className="flex max-h-dialog max-w-dialog-wide flex-col overflow-hidden"
      contentClassName="min-h-0 flex-1 p-0"
    >
      <div className="scrollbar-thin h-full overflow-y-auto p-ui-lg">
        <p className="mb-ui-md font-sans text-product-small leading-5 text-muted-foreground">
          Understand how output contracts, parsed JSON and validation work.
        </p>

        <div className="grid gap-ui-md">
          <HelpSection title="What the output contract is">
            <p>The output contract defines the JSON shape the model is expected to return. It is a runtime agreement between your Agent and downstream code: fields, types and validation rules.</p>
            <p>When JSON output is enabled, the runtime asks the model for valid JSON, parses the final answer and validates the parsed object against this contract.</p>
          </HelpSection>

          <div className="grid gap-ui-md md:grid-cols-3">
            <SectionBlock title="Contract" density="compact" actions={<Badge variant="outline" size="compact">Schema</Badge>}>
              <JsonCodeBlock value={validContract} maxHeight={woobeLayout.codeStructuredDefault} actions={['copy', 'format']} />
            </SectionBlock>
            <SectionBlock title="Valid output" density="compact" actions={<Badge variant="success" size="compact">Valid</Badge>}>
              <JsonCodeBlock value={validOutput} maxHeight={woobeLayout.codeStructuredDefault} actions={['copy', 'format']} />
            </SectionBlock>
            <SectionBlock title="Invalid output" density="compact" actions={<Badge variant="destructive" size="compact">Invalid</Badge>}>
              <JsonCodeBlock value={invalidOutput} maxHeight={woobeLayout.codeStructuredDefault} actions={['copy', 'format']} />
            </SectionBlock>
          </div>

          <HelpSection title="Type names are declarations, not literal values">
            <p>Values like <code>"string"</code>, <code>"number"</code> and <code>"float"</code> declare expected types. The model must return a value of that type rather than the declaration word.</p>
            <div className="grid gap-ui-xs">
              <TechnicalListItem label={<code>"message": "string"</code>} description={<>means text such as <code>"ok"</code>.</>} />
              <TechnicalListItem label={<code>"confidence": "float"</code>} description={<>means a JSON number such as <code>0.87</code>.</>} />
              <TechnicalListItem label={<code>"confidence": "number"</code>} description="in final output is invalid because it is a string." />
            </div>
          </HelpSection>

          <HelpSection title="Supported type declarations">
            <p>The contract accepts direct type names and aliases that are normalized before validation.</p>
            <JsonCodeBlock value={typeAliases} maxHeight={woobeLayout.codeEditorMax} actions={['copy', 'format']} />
          </HelpSection>

          <HelpSection title="Strict validation">
            <p>Strict validation is always active when JSON output is enabled. Invalid JSON or an incompatible response fails the request instead of passing an unreliable shape downstream.</p>
          </HelpSection>

          <HelpSection title="answer, parsed_output and output_parse_error">
            <p><code>answer</code> is the raw model text. <code>parsed_output</code> is the parsed JSON object. <code>output_parse_error</code> describes parsing or validation failures.</p>
            <div className="grid gap-ui-md md:grid-cols-2">
              <SectionBlock title="Successful parse" density="compact" actions={<Badge variant="success" size="compact">Success</Badge>}>
                <JsonCodeBlock value={parsedOutputExample} maxHeight={woobeLayout.codeEditorMax} actions={['copy', 'format']} />
              </SectionBlock>
              <SectionBlock title="Validation failure" density="compact" actions={<Badge variant="warning" size="compact">Failure</Badge>}>
                <JsonCodeBlock value={invalidParsedOutputExample} maxHeight={woobeLayout.codeEditorMax} actions={['copy', 'format']} />
              </SectionBlock>
            </div>
          </HelpSection>
        </div>
      </div>
    </Dialog>
  )
}
