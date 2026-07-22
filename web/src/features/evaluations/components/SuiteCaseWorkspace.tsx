import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  Plus,
  Search,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import type {
  EvaluationCaseInput,
  EvaluationCaseType,
  ExpectedOutcome,
  SuiteValidationResult,
} from '@/features/evaluations/types'
import { cn } from '@/lib/utils'

const caseTypes: Array<{ value: EvaluationCaseType; label: string }> = [
  { value: 'success', label: 'Successful response' },
  { value: 'refusal', label: 'Safe refusal' },
  { value: 'handled_error', label: 'Handled error' },
  { value: 'expected_failure', label: 'Expected runtime failure' },
]

const severityOptions = [
  { value: 'low', label: 'Low' },
  { value: 'normal', label: 'Normal' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
]

function emptyOutcome(type: EvaluationCaseType): ExpectedOutcome {
  return {
    type,
    allowed_failure_origins: [],
    allowed_failure_stages: [],
    allowed_failure_codes: [],
    required_behavior: [],
    forbidden_behavior: [],
  }
}

function emptyCase(index: number, type: EvaluationCaseType = 'success'): EvaluationCaseInput {
  return {
    name: `Question ${index}`,
    case_type: type,
    message: '',
    initial_context: undefined,
    expected_outcome: emptyOutcome(type),
    expected_contract: {
      semantic_criteria: [],
      tools: { required: [], forbidden: [] },
      output_contract: { required: type !== 'expected_failure' },
    },
    severity: 'normal',
    weight: 1,
    blocking: false,
    tags: [],
    production_frequency: null,
  }
}

function lineList(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join('\n')
  if (typeof value === 'string') return value
  return ''
}

function fromLines(value: string): string[] {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

function csv(value: unknown): string {
  return Array.isArray(value) ? value.map(String).join(', ') : ''
}

function fromCsv(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

function issuesByCase(validation: SuiteValidationResult | null) {
  const result = new Map<number, string[]>()
  for (const issue of validation?.errors || []) {
    const match = issue.path?.match(/^cases\[(\d+)\]/)
    if (!match) continue
    const index = Number(match[1])
    result.set(index, [...(result.get(index) || []), issue.message])
  }
  return result
}

interface Props {
  cases: EvaluationCaseInput[]
  validation: SuiteValidationResult | null
  onChange: (cases: EvaluationCaseInput[]) => void
}

export function SuiteCaseWorkspace({ cases, validation, onChange }: Props) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [search, setSearch] = useState('')
  const [contextText, setContextText] = useState('')
  const issueMap = useMemo(() => issuesByCase(validation), [validation])
  const selected = cases[selectedIndex] || cases[0]

  useEffect(() => {
    if (selectedIndex >= cases.length) setSelectedIndex(Math.max(0, cases.length - 1))
  }, [cases.length, selectedIndex])

  useEffect(() => {
    setContextText(selected?.initial_context ? JSON.stringify(selected.initial_context, null, 2) : '')
  }, [selectedIndex, selected?.initial_context])

  const visible = cases
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => {
      const value = `${item.name} ${item.message} ${item.case_type || ''}`.toLowerCase()
      return value.includes(search.trim().toLowerCase())
    })

  if (!selected) return null

  const patch = (values: Partial<EvaluationCaseInput>) => {
    onChange(cases.map((item, index) => index === selectedIndex ? { ...item, ...values } : item))
  }
  const type = selected.case_type || 'success'
  const expected = selected.expected_outcome || emptyOutcome(type)
  const contract = selected.expected_contract || {}
  const tools = (
    contract.tools && typeof contract.tools === 'object'
      ? contract.tools
      : { required: [], forbidden: [] }
  ) as Record<string, unknown>
  const selectedIssues = issueMap.get(selectedIndex) || []

  const updateContext = () => {
    if (!contextText.trim()) {
      patch({ initial_context: undefined })
      return
    }
    try {
      const parsed = JSON.parse(contextText)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('Initial context must be a JSON object')
      }
      patch({ initial_context: parsed })
      toast.success('Initial context updated')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Invalid initial context JSON')
    }
  }

  const addCase = (nextType: EvaluationCaseType) => {
    const next = [...cases, emptyCase(cases.length + 1, nextType)]
    onChange(next)
    setSelectedIndex(next.length - 1)
  }

  const duplicateSelected = () => {
    const duplicate: EvaluationCaseInput = {
      ...selected,
      name: `${selected.name} copy`,
      expected_outcome: selected.expected_outcome
        ? { ...selected.expected_outcome }
        : undefined,
      expected_contract: selected.expected_contract
        ? JSON.parse(JSON.stringify(selected.expected_contract))
        : undefined,
      initial_context: selected.initial_context
        ? JSON.parse(JSON.stringify(selected.initial_context))
        : undefined,
      tags: [...(selected.tags || [])],
    }
    const next = [...cases]
    next.splice(selectedIndex + 1, 0, duplicate)
    onChange(next)
    setSelectedIndex(selectedIndex + 1)
  }

  const deleteSelected = () => {
    if (cases.length === 1) return
    const next = cases.filter((_, index) => index !== selectedIndex)
    onChange(next)
    setSelectedIndex(Math.max(0, selectedIndex - 1))
  }

  return (
    <section className="overflow-hidden rounded-xl border border-border/80 bg-background/30">
      <div className="grid min-h-[620px] lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="border-b border-border/80 bg-surface/25 lg:border-b-0 lg:border-r">
          <div className="border-b border-border/70 p-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search cases"
                className="pl-9"
              />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <Button size="sm" variant="outline" onClick={() => addCase('success')}>
                <Plus className="mr-1.5 h-3.5 w-3.5" />Success
              </Button>
              <Button size="sm" variant="outline" onClick={() => addCase('refusal')}>
                <Plus className="mr-1.5 h-3.5 w-3.5" />Refusal
              </Button>
              <Button size="sm" variant="outline" onClick={() => addCase('handled_error')}>
                <Plus className="mr-1.5 h-3.5 w-3.5" />Handled error
              </Button>
              <Button size="sm" variant="outline" onClick={() => addCase('expected_failure')}>
                <Plus className="mr-1.5 h-3.5 w-3.5" />Failure
              </Button>
            </div>
          </div>
          <div className="max-h-[510px] space-y-1 overflow-y-auto p-2">
            {visible.map(({ item, index }) => {
              const hasError = issueMap.has(index)
              return (
                <button
                  key={`${index}-${item.name}`}
                  type="button"
                  onClick={() => setSelectedIndex(index)}
                  className={cn(
                    'w-full rounded-lg border px-3 py-3 text-left transition-colors',
                    selectedIndex === index
                      ? 'border-primary/35 bg-primary/[0.08]'
                      : 'border-transparent hover:border-border hover:bg-surface/40',
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-medium text-white">
                        {String(index + 1).padStart(2, '0')} · {item.name || 'Untitled case'}
                      </p>
                      <p className="mt-1 truncate text-[10px] text-muted">
                        {(item.case_type || 'success').replaceAll('_', ' ')}
                        {item.blocking ? ' · blocking' : ''}
                      </p>
                    </div>
                    {hasError ? (
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-red-300" />
                    ) : validation ? (
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-300" />
                    ) : null}
                  </div>
                </button>
              )
            })}
          </div>
        </aside>

        <div className="min-w-0 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-semibold text-white">Case {selectedIndex + 1}</h4>
                <Badge variant="outline">{type.replaceAll('_', ' ')}</Badge>
              </div>
              <p className="mt-1 text-[10px] text-muted">
                Only the selected case is expanded. Changes are kept in the Suite draft.
              </p>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={duplicateSelected}>
                <Copy className="mr-1.5 h-3.5 w-3.5" />Duplicate
              </Button>
              <Button size="sm" variant="ghost" disabled={cases.length === 1} onClick={deleteSelected}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {selectedIssues.length ? (
            <div className="mt-4 rounded-lg border border-red-500/20 bg-red-500/[0.04] p-3">
              {selectedIssues.map((issue, index) => (
                <p key={index} className="text-[10px] leading-4 text-red-300">{issue}</p>
              ))}
            </div>
          ) : null}

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-xs text-muted">
              <span>Case name</span>
              <Input value={selected.name} onChange={(event) => patch({ name: event.target.value })} />
            </label>
            <label className="space-y-2 text-xs text-muted">
              <span>Expected outcome type</span>
              <Select
                value={type}
                onChange={(event) => {
                  const next = event.target.value as EvaluationCaseType
                  patch({
                    case_type: next,
                    expected_outcome: emptyOutcome(next),
                    expected_contract: {
                      ...contract,
                      output_contract: {
                        ...((contract.output_contract || {}) as Record<string, unknown>),
                        required: next !== 'expected_failure',
                      },
                    },
                  })
                }}
                options={caseTypes}
              />
            </label>
          </div>

          <label className="mt-4 block space-y-2 text-xs text-muted">
            <span>Question or input sent to the target</span>
            <textarea
              value={selected.message}
              onChange={(event) => patch({ message: event.target.value })}
              placeholder="Example: How can I update my billing address?"
              className="min-h-24 w-full rounded-lg border border-border bg-background p-3 text-sm text-white outline-none focus:border-primary/40"
            />
          </label>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-xs text-muted">
              <span>Required behavior · one item per line</span>
              <textarea
                value={lineList(expected.required_behavior)}
                onChange={(event) => patch({
                  expected_outcome: {
                    ...expected,
                    required_behavior: fromLines(event.target.value),
                  },
                })}
                placeholder="Explain the supported process\nAsk for missing information"
                className="min-h-28 w-full rounded-lg border border-border bg-background p-3 text-sm text-white outline-none focus:border-primary/40"
              />
            </label>
            <label className="space-y-2 text-xs text-muted">
              <span>Forbidden behavior · one item per line</span>
              <textarea
                value={lineList(expected.forbidden_behavior)}
                onChange={(event) => patch({
                  expected_outcome: {
                    ...expected,
                    forbidden_behavior: fromLines(event.target.value),
                  },
                })}
                placeholder="Do not invent customer data\nDo not claim an action was completed"
                className="min-h-28 w-full rounded-lg border border-border bg-background p-3 text-sm text-white outline-none focus:border-primary/40"
              />
            </label>
          </div>

          <label className="mt-4 block space-y-2 text-xs text-muted">
            <span>Semantic grading criteria · one item per line</span>
            <textarea
              value={lineList(contract.semantic_criteria)}
              onChange={(event) => patch({
                expected_contract: {
                  ...contract,
                  semantic_criteria: fromLines(event.target.value),
                },
              })}
              placeholder="The answer must directly address the question\nThe answer must remain grounded in available evidence"
              className="min-h-24 w-full rounded-lg border border-border bg-background p-3 text-sm text-white outline-none focus:border-primary/40"
            />
          </label>

          {type === 'expected_failure' ? (
            <section className="mt-4 rounded-lg border border-amber-500/20 bg-amber-500/[0.04] p-4">
              <p className="text-xs font-medium text-white">Expected failure contract</p>
              <p className="mt-1 text-[10px] text-muted">
                Specify at least one allowed origin, stage or stable failure code.
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <label className="space-y-2 text-[10px] text-muted">
                  <span>Origins</span>
                  <Input
                    value={csv(expected.allowed_failure_origins)}
                    onChange={(event) => patch({
                      expected_outcome: {
                        ...expected,
                        allowed_failure_origins: fromCsv(event.target.value),
                      },
                    })}
                    placeholder="tool, provider"
                  />
                </label>
                <label className="space-y-2 text-[10px] text-muted">
                  <span>Stages</span>
                  <Input
                    value={csv(expected.allowed_failure_stages)}
                    onChange={(event) => patch({
                      expected_outcome: {
                        ...expected,
                        allowed_failure_stages: fromCsv(event.target.value),
                      },
                    })}
                    placeholder="tool_execution"
                  />
                </label>
                <label className="space-y-2 text-[10px] text-muted">
                  <span>Codes</span>
                  <Input
                    value={csv(expected.allowed_failure_codes)}
                    onChange={(event) => patch({
                      expected_outcome: {
                        ...expected,
                        allowed_failure_codes: fromCsv(event.target.value),
                      },
                    })}
                    placeholder="tool_timeout"
                  />
                </label>
              </div>
            </section>
          ) : null}

          <details className="mt-5 rounded-lg border border-border/80 bg-surface/20 p-4">
            <summary className="cursor-pointer text-xs font-medium text-white">
              Tools, context and scoring settings
            </summary>
            <div className="mt-4 space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <label className="space-y-2 text-xs text-muted">
                  <span>Required Tools · one exact name per line</span>
                  <textarea
                    value={lineList(tools.required)}
                    onChange={(event) => patch({
                      expected_contract: {
                        ...contract,
                        tools: { ...tools, required: fromLines(event.target.value) },
                      },
                    })}
                    className="min-h-20 w-full rounded-lg border border-border bg-background p-3 text-xs text-white outline-none"
                  />
                </label>
                <label className="space-y-2 text-xs text-muted">
                  <span>Forbidden Tools · one exact name per line</span>
                  <textarea
                    value={lineList(tools.forbidden)}
                    onChange={(event) => patch({
                      expected_contract: {
                        ...contract,
                        tools: { ...tools, forbidden: fromLines(event.target.value) },
                      },
                    })}
                    className="min-h-20 w-full rounded-lg border border-border bg-background p-3 text-xs text-white outline-none"
                  />
                </label>
              </div>

              <label className="block space-y-2 text-xs text-muted">
                <span>Initial context · JSON object</span>
                <textarea
                  value={contextText}
                  onChange={(event) => setContextText(event.target.value)}
                  onBlur={updateContext}
                  placeholder={'{\n  "customer_authenticated": true\n}'}
                  className="min-h-24 w-full rounded-lg border border-border bg-background p-3 font-mono text-xs text-white outline-none"
                />
              </label>

              <div className="grid gap-4 sm:grid-cols-4">
                <label className="space-y-2 text-xs text-muted">
                  <span>Severity</span>
                  <Select
                    value={selected.severity || 'normal'}
                    onChange={(event) => patch({ severity: event.target.value as EvaluationCaseInput['severity'] })}
                    options={severityOptions}
                  />
                </label>
                <label className="space-y-2 text-xs text-muted">
                  <span>Weight</span>
                  <Input
                    type="number"
                    min={0.1}
                    max={100}
                    step={0.1}
                    value={selected.weight || 1}
                    onChange={(event) => patch({ weight: Number(event.target.value) })}
                  />
                </label>
                <label className="space-y-2 text-xs text-muted">
                  <span>Production frequency</span>
                  <Input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={selected.production_frequency ?? ''}
                    onChange={(event) => patch({
                      production_frequency: event.target.value === '' ? null : Number(event.target.value),
                    })}
                    placeholder="0.00–1.00"
                  />
                </label>
                <label className="space-y-2 text-xs text-muted">
                  <span>Blocking</span>
                  <span className="flex h-10 items-center gap-2 rounded-lg border border-border bg-background px-3">
                    <input
                      type="checkbox"
                      checked={Boolean(selected.blocking)}
                      onChange={(event) => patch({ blocking: event.target.checked })}
                    />
                    Critical gate
                  </span>
                </label>
              </div>

              <label className="block space-y-2 text-xs text-muted">
                <span>Tags · comma separated</span>
                <Input
                  value={csv(selected.tags)}
                  onChange={(event) => patch({ tags: fromCsv(event.target.value) })}
                  placeholder="billing, security, regression"
                />
              </label>
            </div>
          </details>
        </div>
      </div>
    </section>
  )
}

export { emptyCase, emptyOutcome }
