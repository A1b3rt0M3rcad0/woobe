import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Gauge, ServerCog } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { useProviderModels } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'
import {
  calculateContextCapacity,
  presetInputBudget,
  providerModelCapabilities,
  readContextBudget,
  withContextBudget,
  type ContextCapacity,
} from './contextBudget'

type BudgetMode = 'auto' | 'fixed'
type BudgetPreset = 'auto' | '25' | '50' | '75' | '90' | 'custom'

function formatUnits(value: number | null | undefined): string {
  return value == null ? 'Unavailable' : new Intl.NumberFormat('en-US').format(value)
}

function formatPercent(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function CapacityRow({ label, value, muted = false }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 text-[11px]">
      <span className="text-muted">{label}</span>
      <span className={cn('font-mono', muted ? 'text-muted' : 'text-foreground')}>{value}</span>
    </div>
  )
}

function CapacityCard({
  title,
  model,
  capacity,
  isFallback = false,
}: {
  title: string
  model: ProviderModel | null
  capacity: ContextCapacity | null
  isFallback?: boolean
}) {
  if (!model || !capacity) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-background/30 p-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">{title}</p>
        <p className="mt-2 text-xs text-muted">{isFallback ? 'No fallback model configured.' : 'No primary model configured.'}</p>
      </div>
    )
  }

  const status = capacity.contextWindow == null
    ? 'Capacity unknown'
    : capacity.budgetClamped
      ? 'Limited by model capacity'
      : 'Full configured budget available'

  return (
    <div className="rounded-lg border border-border bg-background/35 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">{title}</p>
          <p className="mt-1 truncate text-xs font-medium text-foreground">{model.name}</p>
          <p className="truncate font-mono text-[10px] text-muted">{model.model}</p>
        </div>
        <span className={cn(
          'shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-medium',
          capacity.contextWindow == null
            ? 'border-amber-500/25 bg-amber-500/10 text-amber-300'
            : capacity.budgetClamped
              ? 'border-amber-500/25 bg-amber-500/10 text-amber-300'
              : 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300',
        )}>
          {status}
        </span>
      </div>

      <div className="mt-3 space-y-1.5 border-t border-border/70 pt-3">
        <CapacityRow label="Model context window" value={formatUnits(capacity.contextWindow)} />
        <CapacityRow label="Model max output" value={formatUnits(capacity.modelMaxOutputTokens)} muted={capacity.modelMaxOutputTokens == null} />
        <CapacityRow label="Effective output reserve" value={formatUnits(capacity.effectiveOutputReserve)} />
        <CapacityRow label="Maximum input capacity" value={formatUnits(capacity.modelUsableInput)} />
        <CapacityRow label="Configured context budget" value={capacity.configuredInputBudget == null ? 'Auto' : formatUnits(capacity.configuredInputBudget)} />
        <CapacityRow label="Effective context budget" value={formatUnits(capacity.effectiveInputBudget)} />
        {isFallback && capacity.budgetPreservationRatio != null ? (
          <CapacityRow label="Configured budget preservation" value={formatPercent(capacity.budgetPreservationRatio)} />
        ) : null}
      </div>
    </div>
  )
}

export function AgentContextConfigurationDialog({
  open,
  onClose,
  projectId,
  managerName,
}: {
  open: boolean
  onClose: () => void
  projectId: string
  managerName: string
}) {
  const { state, setField } = useAgentEditor()
  const { data: providerModels = [] } = useProviderModels(projectId)
  const savedBudget = useMemo(() => readContextBudget(state.runtimeConfig), [state.runtimeConfig])
  const [budgetMode, setBudgetMode] = useState<BudgetMode>('auto')
  const [preset, setPreset] = useState<BudgetPreset>('auto')
  const [inputBudget, setInputBudget] = useState(256)
  const [runtimeReserve, setRuntimeReserve] = useState(0)
  const [temperature, setTemperature] = useState(0.7)
  const [maxOutputTokens, setMaxOutputTokens] = useState(2048)

  useEffect(() => {
    if (!open) return
    const fixed = savedBudget.maxInputUnits != null
    setBudgetMode(fixed ? 'fixed' : 'auto')
    setPreset(fixed ? 'custom' : 'auto')
    setInputBudget(savedBudget.maxInputUnits ?? 256)
    setRuntimeReserve(savedBudget.runtimeReserveUnits)
    setTemperature(state.temperature)
    setMaxOutputTokens(state.maxOutputTokens)
  }, [open, savedBudget.maxInputUnits, savedBudget.runtimeReserveUnits, state.maxOutputTokens, state.temperature])

  const primaryModel = providerModels.find((model) => model.id === state.providerModelId) || null
  const fallbackModel = providerModels.find((model) => model.id === state.fallbackProviderModelId) || null
  const primaryCapabilities = providerModelCapabilities(primaryModel)
  const fallbackCapabilities = providerModelCapabilities(fallbackModel)
  const configuredInputBudget = budgetMode === 'auto' ? null : inputBudget

  const primaryCapacity = primaryModel
    ? calculateContextCapacity({
        contextWindow: primaryCapabilities.contextWindow,
        modelMaxOutputTokens: primaryCapabilities.maxOutputTokens,
        configuredOutputTokens: maxOutputTokens,
        runtimeReserveUnits: runtimeReserve,
        configuredInputBudget,
      })
    : null
  const fallbackCapacity = fallbackModel
    ? calculateContextCapacity({
        contextWindow: fallbackCapabilities.contextWindow,
        modelMaxOutputTokens: fallbackCapabilities.maxOutputTokens,
        configuredOutputTokens: maxOutputTokens,
        runtimeReserveUnits: runtimeReserve,
        configuredInputBudget,
      })
    : null
  const primaryAutoCapacity = primaryModel
    ? calculateContextCapacity({
        contextWindow: primaryCapabilities.contextWindow,
        modelMaxOutputTokens: primaryCapabilities.maxOutputTokens,
        configuredOutputTokens: maxOutputTokens,
        runtimeReserveUnits: runtimeReserve,
        configuredInputBudget: null,
      })
    : null

  const fixedBudgetValid = budgetMode === 'auto'
    || (Number.isInteger(inputBudget) && inputBudget >= 256 && inputBudget <= 4_000_000)
  const reserveValid = Number.isInteger(runtimeReserve) && runtimeReserve >= 0 && runtimeReserve <= 1_000_000
  const outputValid = Number.isInteger(maxOutputTokens) && maxOutputTokens >= 1
  const temperatureValid = Number.isFinite(temperature) && temperature >= 0 && temperature <= 2
  const canApply = fixedBudgetValid && reserveValid && outputValid && temperatureValid
  const percentageAvailable = (primaryAutoCapacity?.modelUsableInput ?? 0) >= 256

  const choosePreset = (nextPreset: BudgetPreset) => {
    setPreset(nextPreset)
    if (nextPreset === 'auto') {
      setBudgetMode('auto')
      return
    }
    setBudgetMode('fixed')
    if (nextPreset === 'custom') return
    const ratio = Number(nextPreset) / 100
    const calculated = presetInputBudget(primaryAutoCapacity?.modelUsableInput ?? null, ratio)
    if (calculated != null) setInputBudget(calculated)
  }

  const apply = () => {
    if (!canApply) return
    setField('runtimeConfig', withContextBudget(state.runtimeConfig, {
      maxInputUnits: budgetMode === 'auto' ? null : inputBudget,
      runtimeReserveUnits: runtimeReserve,
    }))
    setField('temperature', temperature)
    setField('maxOutputTokens', maxOutputTokens)
    onClose()
  }

  const capacityUnknown = primaryModel != null && primaryCapabilities.contextWindow == null
  const fallbackSmaller = fallbackCapacity?.effectiveInputBudget != null
    && primaryCapacity?.effectiveInputBudget != null
    && fallbackCapacity.effectiveInputBudget < primaryCapacity.effectiveInputBudget

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Context Configuration"
      className="max-w-[860px] overflow-hidden bg-surface/95"
      contentClassName="p-0"
    >
      <div className="max-h-[min(760px,calc(100svh-7rem))] overflow-y-auto px-5 py-4">
        <div className="rounded-lg border border-border bg-background/30 px-3.5 py-3">
          <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-muted">Context manager</p>
          <p className="mt-1 text-sm font-semibold text-foreground">{managerName}</p>
          <p className="mt-1 text-[10px] leading-4 text-muted">This configuration belongs to the Agent Context Policy and remains independent from changing the concrete manager strategy.</p>
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section className="rounded-xl border border-border bg-background/20 p-4">
            <div className="flex items-center gap-2">
              <Gauge className="h-4 w-4 text-primary-light" />
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">Context Budget</p>
            </div>

            <div className="mt-3">
              <label className="text-xs font-medium text-muted">Input Context Budget</label>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(['auto', '25', '50', '75', '90', 'custom'] as BudgetPreset[]).map((item) => {
                  const percentage = item !== 'auto' && item !== 'custom'
                  return (
                    <Button
                      key={item}
                      type="button"
                      size="sm"
                      variant={preset === item ? 'default' : 'outline'}
                      className="h-7 px-2.5 text-[10px]"
                      disabled={percentage && !percentageAvailable}
                      onClick={() => choosePreset(item)}
                    >
                      {item === 'auto' ? 'Auto' : item === 'custom' ? 'Custom' : `${item}%`}
                    </Button>
                  )
                })}
              </div>
              <p className="mt-2 text-[10px] leading-4 text-muted">Percentage presets are converted to an absolute Draft value so Releases remain deterministic.</p>
            </div>

            {budgetMode === 'fixed' ? (
              <label className="mt-3 block text-xs font-medium text-muted">
                Context budget units
                <Input
                  type="number"
                  min="256"
                  max="4000000"
                  step="1"
                  className="mt-1"
                  value={inputBudget}
                  onChange={(event) => {
                    setPreset('custom')
                    setInputBudget(Number(event.target.value))
                  }}
                />
                {!fixedBudgetValid ? <span className="mt-1 block text-[10px] text-red-300">Use an integer between 256 and 4,000,000.</span> : null}
              </label>
            ) : null}

            <label className="mt-3 block text-xs font-medium text-muted">
              Runtime Reserve
              <Input
                type="number"
                min="0"
                max="1000000"
                step="1"
                className="mt-1"
                value={runtimeReserve}
                onChange={(event) => setRuntimeReserve(Number(event.target.value))}
              />
              <span className="mt-1 block text-[10px] leading-4 text-muted">Reserved from the model window before materializing input context.</span>
              {!reserveValid ? <span className="mt-1 block text-[10px] text-red-300">Use an integer from 0 to 1,000,000.</span> : null}
            </label>
          </section>

          <section className="rounded-xl border border-border bg-background/20 p-4">
            <div className="flex items-center gap-2">
              <ServerCog className="h-4 w-4 text-primary-light" />
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">Generation</p>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <label className="text-xs font-medium text-muted">
                Temperature
                <Input
                  type="number"
                  min="0"
                  max="2"
                  step="0.1"
                  className="mt-1"
                  value={temperature}
                  onChange={(event) => setTemperature(Number(event.target.value))}
                />
              </label>
              <label className="text-xs font-medium text-muted">
                Max Output Tokens
                <Input
                  type="number"
                  min="1"
                  step="1"
                  className="mt-1"
                  value={maxOutputTokens}
                  onChange={(event) => setMaxOutputTokens(Number(event.target.value))}
                />
              </label>
            </div>
            {!temperatureValid ? <p className="mt-2 text-[10px] text-red-300">Temperature must be between 0 and 2.</p> : null}
            {!outputValid ? <p className="mt-2 text-[10px] text-red-300">Max Output Tokens must be a positive integer.</p> : null}
            <p className="mt-3 text-[10px] leading-4 text-muted">At runtime the configured output is clamped to each invoked model capability. Primary and fallback may therefore reserve different output budgets.</p>
          </section>
        </div>

        <section className="mt-4 rounded-xl border border-border bg-background/20 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Capacity Preview</p>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            <CapacityCard title="Primary model" model={primaryModel} capacity={primaryCapacity} />
            <CapacityCard title="Fallback model" model={fallbackModel} capacity={fallbackCapacity} isFallback />
          </div>

          {capacityUnknown ? (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-[10px] leading-4 text-amber-200">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Primary model context capacity is not configured. Absolute budgets can still be enforced, but Auto and percentage presets cannot guarantee provider-window compatibility.
            </div>
          ) : null}
          {fallbackSmaller ? (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-[10px] leading-4 text-amber-200">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              The fallback has a smaller effective context capacity. On fallback, the Context Manager will re-materialize context against that invocation-specific budget and may reduce non-mandatory sources.
            </div>
          ) : null}
        </section>
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-border/90 bg-background/20 px-4 py-3">
        <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
        <Button type="button" onClick={apply} disabled={!canApply}>Apply</Button>
      </div>
    </Dialog>
  )
}
