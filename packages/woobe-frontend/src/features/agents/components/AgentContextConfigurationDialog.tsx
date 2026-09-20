import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Gauge, ServerCog } from 'lucide-react'
import {
  Alert,
  AlertDescription,
  Badge,
  Button,
  Dialog,
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
  Input,
  SectionBlock,
  SegmentedControl,
  TechnicalListItem,
} from '@woobe/ui'

import { useProviderModels } from '@/features/provider-models/hooks'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { ModelSettingsModal } from '@/features/provider-models/components/ModelSettingsModal'
import type { ProviderModel } from '@/features/provider-models/types'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
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

const NUMBER_INPUT_CLASS = '[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none'

function formatUnits(value: number | null | undefined): string {
  return value == null ? 'Unavailable' : new Intl.NumberFormat('en-US').format(value)
}

function formatPercent(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function Help({ text, label }: { text: string; label: string }) {
  return (
    <span
      className="cursor-help select-none font-mono text-system-meta font-medium text-muted-foreground transition-colors hover:text-primary-light focus:text-primary-light focus:outline-none"
      title={text}
      tabIndex={0}
      aria-label={`${label}: ${text}`}
    >
      (?)
    </span>
  )
}

function CapacityRow({
  label,
  value,
  help,
  muted = false,
}: {
  label: string
  value: string
  help: string
  muted?: boolean
}) {
  return (
    <div className="flex items-center justify-between gap-ui-md border-b border-border/60 py-ui-xs last:border-b-0">
      <span className="inline-flex min-w-0 items-center gap-ui-xs font-sans text-product-caption text-muted-foreground">
        <span>{label}</span>
        <Help text={help} label={label} />
      </span>
      <span className={`shrink-0 font-mono text-system-control ${muted ? 'text-muted-foreground' : 'text-accent-foreground'}`}>{value}</span>
    </div>
  )
}

function CapacityCard({
  title,
  model,
  capacity,
  isFallback = false,
  onConfigure,
}: {
  title: string
  model: ProviderModel | null
  capacity: ContextCapacity | null
  isFallback?: boolean
  onConfigure: () => void
}) {
  if (!model || !capacity) {
    return (
      <div className="rounded-container border border-dashed border-border bg-background/25 p-ui-md">
        <p className="font-mono text-system-label font-semibold uppercase tracking-system-label text-muted-foreground">{title}</p>
        <p className="mt-ui-sm font-sans text-product-caption text-muted-foreground">{isFallback ? 'No fallback model configured.' : 'No primary model configured.'}</p>
      </div>
    )
  }

  const status = capacity.contextWindow == null
    ? 'Capacity unknown'
    : capacity.budgetClamped
      ? 'Limited by model capacity'
      : 'Full configured budget available'
  const warning = capacity.contextWindow == null || capacity.budgetClamped

  return (
    <div className="rounded-container border border-border bg-background/25 p-ui-md">
      <TechnicalListItem
        label={model.name}
        description={model.model}
        meta={title}
        trailing={<Badge variant={warning ? 'warning' : 'success'} size="compact">{status}</Badge>}
      />

      <div className="mt-ui-md border-t border-border pt-ui-sm">
        <CapacityRow
          label="Model context window"
          value={formatUnits(capacity.contextWindow)}
          help="Maximum context window supported by this model according to its ProviderModel capability metadata."
        />
        <CapacityRow
          label="Model max output"
          value={formatUnits(capacity.modelMaxOutputTokens)}
          help="Maximum response size supported by this model. Woobe will not request more output than this capability allows."
          muted={capacity.modelMaxOutputTokens == null}
        />
        <CapacityRow
          label="Effective output reserve"
          value={formatUnits(capacity.effectiveOutputReserve)}
          help="Output tokens Woobe reserves for this model invocation after applying the model maximum to the configured Max Output Tokens."
        />
        <CapacityRow
          label="Maximum input capacity"
          value={formatUnits(capacity.modelUsableInput)}
          help="Maximum input context available after subtracting output and runtime reserves from the model context window."
        />
        <CapacityRow
          label="Configured context budget"
          value={capacity.configuredInputBudget == null ? 'Auto' : formatUnits(capacity.configuredInputBudget)}
          help="The input context limit configured for this Agent. Auto uses the available capacity of each model invocation."
        />
        <CapacityRow
          label="Effective context budget"
          value={formatUnits(capacity.effectiveInputBudget)}
          help="The final input context budget Woobe can use for this invocation after applying the configured budget and model capacity limits."
        />
        {isFallback && capacity.budgetPreservationRatio != null ? (
          <CapacityRow
            label="Configured budget preservation"
            value={formatPercent(capacity.budgetPreservationRatio)}
            help="How much of the configured context budget this fallback model can preserve when its available context capacity is smaller."
          />
        ) : null}
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="mt-ui-md"
        aria-label={`Configure capacity for ${title.toLowerCase()}`}
        onClick={onConfigure}
      >
        Configure capacity
      </Button>
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
  const { data: providerModels = [], refetch: refetchModels } = useProviderModels(projectId)
  const [capacityModel, setCapacityModel] = useState<ProviderModel | null>(null)
  const { data: credentials } = useCredentials(open && capacityModel ? projectId : undefined)
  const savedBudget = useMemo(() => readContextBudget(state.runtimeConfig), [state.runtimeConfig])
  const [budgetMode, setBudgetMode] = useState<BudgetMode>('auto')
  const [preset, setPreset] = useState<BudgetPreset>('auto')
  const [inputBudget, setInputBudget] = useState(256)
  const [runtimeReserve, setRuntimeReserve] = useState(0)
  const [temperature, setTemperature] = useState(0.7)
  const [maxOutputTokens, setMaxOutputTokens] = useState(2048)

  useEffect(() => {
    if (!open) {
      setCapacityModel(null)
      return
    }
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

  const modelsWithoutCapacity = [primaryModel, fallbackModel].filter(
    (model): model is ProviderModel => model != null && providerModelCapabilities(model).contextWindow == null,
  )
  const fallbackSmaller = fallbackCapacity?.effectiveInputBudget != null
    && primaryCapacity?.effectiveInputBudget != null
    && fallbackCapacity.effectiveInputBudget < primaryCapacity.effectiveInputBudget

  const presetItems = (['auto', '25', '50', '75', '90', 'custom'] as BudgetPreset[]).map((item) => ({
    value: item,
    label: item === 'auto' ? 'Auto' : item === 'custom' ? 'Custom' : `${item}%`,
    disabled: item !== 'auto' && item !== 'custom' && !percentageAvailable,
  }))

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Context Configuration"
      className="flex max-h-dialog max-w-dialog-wide flex-col overflow-hidden"
      contentClassName="min-h-0 flex-1 p-0"
    >
      <div className="min-h-0 flex-1 overflow-y-auto p-ui-lg">
        <div className="grid gap-ui-md">
          <TechnicalListItem
            label={managerName}
            description="This configuration belongs to the Agent Context Policy and remains independent from changing the concrete manager strategy."
            meta="Context manager"
          />

          <div className="grid gap-ui-md lg:grid-cols-2">
            <SectionBlock
              title="Context Budget"
              description="Input materialization limits applied before each model invocation."
              actions={<Gauge className="h-icon w-icon text-primary-light" />}
            >
              <div className="grid gap-ui-md">
                <Field>
                  <div className="flex items-center gap-ui-xs">
                    <FieldLabel>Input Context Budget</FieldLabel>
                    <Help
                      label="Input Context Budget"
                      text="Defines how much input context Woobe may materialize for each model invocation. Auto follows the available capacity; presets and Custom freeze an absolute Draft value."
                    />
                  </div>
                  <SegmentedControl
                    items={presetItems}
                    value={preset}
                    onValueChange={(value) => choosePreset(value as BudgetPreset)}
                    ariaLabel="Input context budget preset"
                    size="compact"
                  />
                  <FieldDescription>Percentage presets are converted to an absolute Draft value so Releases remain deterministic.</FieldDescription>
                </Field>

                {budgetMode === 'fixed' ? (
                  <Field>
                    <div className="flex items-center gap-ui-xs">
                      <FieldLabel>Context budget units</FieldLabel>
                      <Help
                        label="Context budget units"
                        text="Absolute maximum input context units Woobe may materialize for the Agent. For text models these units are used as the pre-call token budget estimate."
                      />
                    </div>
                    <Input
                      aria-label="Context budget units"
                      type="number"
                      min="256"
                      max="4000000"
                      step="1"
                      className={NUMBER_INPUT_CLASS}
                      value={inputBudget}
                      onChange={(event) => {
                        setPreset('custom')
                        setInputBudget(Number(event.target.value))
                      }}
                      invalid={!fixedBudgetValid}
                    />
                    {!fixedBudgetValid ? <FieldError>Use an integer between 256 and 4,000,000.</FieldError> : null}
                  </Field>
                ) : null}

                <Field>
                  <div className="flex items-center gap-ui-xs">
                    <FieldLabel>Runtime Reserve</FieldLabel>
                    <Help
                      label="Runtime Reserve"
                      text="Keeps part of the model context window unavailable to input materialization so the runtime has explicit headroom before the model call."
                    />
                  </div>
                  <Input
                    type="number"
                    min="0"
                    max="1000000"
                    step="1"
                    className={NUMBER_INPUT_CLASS}
                    value={runtimeReserve}
                    onChange={(event) => setRuntimeReserve(Number(event.target.value))}
                    invalid={!reserveValid}
                  />
                  <FieldDescription>Reserved from the model window before materializing input context.</FieldDescription>
                  {!reserveValid ? <FieldError>Use an integer from 0 to 1,000,000.</FieldError> : null}
                </Field>
              </div>
            </SectionBlock>

            <SectionBlock
              title="Generation"
              description="Invocation settings combined with each model capability at runtime."
              actions={<ServerCog className="h-icon w-icon text-primary-light" />}
            >
              <div className="grid gap-ui-md sm:grid-cols-2">
                <Field>
                  <div className="flex items-center gap-ui-xs">
                    <FieldLabel>Temperature</FieldLabel>
                    <Help
                      label="Temperature"
                      text="Controls response variability. Lower values are more deterministic; higher values allow more variation."
                    />
                  </div>
                  <Input
                    type="number"
                    min="0"
                    max="2"
                    step="0.1"
                    className={NUMBER_INPUT_CLASS}
                    value={temperature}
                    onChange={(event) => setTemperature(Number(event.target.value))}
                    invalid={!temperatureValid}
                  />
                  {!temperatureValid ? <FieldError>Temperature must be between 0 and 2.</FieldError> : null}
                </Field>

                <Field>
                  <div className="flex items-center gap-ui-xs">
                    <FieldLabel>Max Output Tokens</FieldLabel>
                    <Help
                      label="Max Output Tokens"
                      text="Maximum response budget requested by the Agent. Woobe automatically reduces it when the invoked primary or fallback model supports a smaller maximum output."
                    />
                  </div>
                  <Input
                    type="number"
                    min="1"
                    step="1"
                    className={NUMBER_INPUT_CLASS}
                    value={maxOutputTokens}
                    onChange={(event) => setMaxOutputTokens(Number(event.target.value))}
                    invalid={!outputValid}
                  />
                  {!outputValid ? <FieldError>Max Output Tokens must be a positive integer.</FieldError> : null}
                </Field>
              </div>
              <FieldDescription className="mt-ui-md">At runtime the configured output is clamped to each invoked model capability. Primary and fallback may therefore reserve different output budgets.</FieldDescription>
            </SectionBlock>
          </div>

          <SectionBlock title="Capacity Preview" description="Effective invocation budgets after model-specific limits are applied.">
            <div className="grid gap-ui-md lg:grid-cols-2">
              <CapacityCard title="Primary model" model={primaryModel} capacity={primaryCapacity} onConfigure={() => setCapacityModel(primaryModel)} />
              <CapacityCard title="Fallback model" model={fallbackModel} capacity={fallbackCapacity} isFallback onConfigure={() => setCapacityModel(fallbackModel)} />
            </div>

            {modelsWithoutCapacity.length > 0 ? (
              <Alert variant="warning" className="mt-ui-md">
                <AlertTriangle className="h-icon w-icon" />
                <AlertDescription>
                  Context Window is missing for {modelsWithoutCapacity.map((model) => model.name).join(', ')}.
                  {' '}{budgetMode === 'auto'
                    ? 'Auto has no effective input budget for these models. Configure their capacity or choose a Custom input budget. Token usage is still counted.'
                    : 'The fixed input budget is enforced, but compatibility with these model windows cannot be checked.'}
                </AlertDescription>
              </Alert>
            ) : null}
            {fallbackSmaller ? (
              <Alert variant="warning" className="mt-ui-md">
                <AlertTriangle className="h-icon w-icon" />
                <AlertDescription>The fallback has a smaller effective context capacity. On fallback, the Context Manager will re-materialize context against that invocation-specific budget and may reduce non-mandatory sources.</AlertDescription>
              </Alert>
            ) : null}
          </SectionBlock>
        </div>
      </div>

      <div className="flex shrink-0 items-center justify-end gap-ui-sm border-t border-border bg-surface/95 px-ui-lg py-ui-md">
        <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
        <Button type="button" onClick={apply} disabled={!canApply}>Apply</Button>
      </div>
      {open && capacityModel ? (
        <ModelSettingsModal
          open
          onClose={() => setCapacityModel(null)}
          projectId={projectId}
          credentials={credentials}
          selectedModel={capacityModel}
          initialSection="capabilities"
          layer="nestedModal"
          onSaved={async () => { await refetchModels() }}
        />
      ) : null}
    </Dialog>
  )
}
