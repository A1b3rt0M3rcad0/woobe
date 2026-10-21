import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button } from '@woobe/ui'
import { AtSign, Braces, ChevronDown, ChevronRight, FilePlus2, Loader2, Paperclip, Send, Square, Wrench, X } from 'lucide-react'

import { ContractValueForm } from '@/features/contracts/ContractValueForm'
import { contractFields } from '@/features/contracts/contractFields'
import { uploadArtifactFile } from '@/features/artifacts/upload'
import { getArtifactCapabilities, listArtifacts } from '@/features/artifacts/api'
import type { ArtifactComposerContext, ArtifactFile, ArtifactPage } from '@/features/artifacts/types'
import { createUuid } from '@/lib/uuid'

export interface ComposerArtifactReference {
  ref: { artifact_id: string; revision_id: string }
  label: string
  content_type?: string
}

interface ChatComposerProps {
  isSending: boolean
  isStopping?: boolean
  isPreparing?: boolean
  onSend: (content: string) => void
  onSendArtifacts?: (content: string, artifacts: ComposerArtifactReference[]) => void
  artifactContext?: ArtifactComposerContext | null
  onStop: () => void
  runtimeBlocked?: boolean
  runtimeBlockReason?: string
  value?: string
  onChange?: (value: string) => void
  placeholder?: string
  statusText?: string
  preparingText?: string
  density?: 'default' | 'compact'
  externalContextContract?: unknown
  externalContextValues?: Record<string, unknown>
  lockedExternalContextValues?: Record<string, unknown>
  onExternalContextValuesChange?: (values: Record<string, unknown>) => void
  onClearExternalContextValues?: () => void
}

export function ChatComposer({
  isSending,
  isStopping = false,
  isPreparing = false,
  onSend,
  onSendArtifacts,
  artifactContext,
  onStop,
  runtimeBlocked = false,
  runtimeBlockReason,
  value,
  onChange,
  placeholder = 'Type your message...',
  statusText,
  preparingText = 'Preparing...',
  density = 'default',
  externalContextContract,
  externalContextValues = {},
  lockedExternalContextValues = {},
  onExternalContextValuesChange,
  onClearExternalContextValues,
}: ChatComposerProps) {
  const [internalInput, setInternalInput] = useState('')
  const [externalContextOpen, setExternalContextOpen] = useState(false)
  const [artifactPickerOpen, setArtifactPickerOpen] = useState(false)
  const [artifactDirectory, setArtifactDirectory] = useState('')
  const [artifactCursor, setArtifactCursor] = useState<string | null>(null)
  const [artifactPage, setArtifactPage] = useState<ArtifactPage | null>(null)
  const [artifactLoading, setArtifactLoading] = useState(false)
  const [artifactLoadError, setArtifactLoadError] = useState(false)
  const [selectedArtifacts, setSelectedArtifacts] = useState<ComposerArtifactReference[]>([])
  const [artifactError, setArtifactError] = useState<string | null>(null)
  const [uploadingFile, setUploadingFile] = useState(false)
  const [pendingAttachment, setPendingAttachment] = useState<{
    file: File
    path: string
    operationId: string
    uploadedBytes: number
  } | null>(null)
  const uploadControllerRef = useRef<AbortController | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const input = value ?? internalInput
  const blocked = isSending || isPreparing || runtimeBlocked || uploadingFile || pendingAttachment !== null
  const canWriteArtifacts = Boolean(artifactContext && (!artifactContext.actions || artifactContext.actions.includes('write')))
  const showUploadControl = !artifactContext || canWriteArtifacts
  const compact = density === 'compact'
  const artifactScope = useMemo(() => artifactContext ? { projectId: artifactContext.projectId, environment: artifactContext.environment } : null,
    [artifactContext?.environment, artifactContext?.projectId])
  const externalContextFields = useMemo(() => contractFields(externalContextContract), [externalContextContract])
  const externalContextFieldEntries = Object.entries(externalContextFields)
  const hasExternalContextValues = Object.keys(externalContextValues).length > 0
  const missingRequiredExternalContextFields = externalContextFieldEntries.filter(([name, field]) => {
    const consumers = field && typeof field === 'object' && 'consumers' in field && field.consumers && typeof field.consumers === 'object' && !Array.isArray(field.consumers)
      ? field.consumers as Record<string, { required?: boolean }>
      : {}
    const required = Boolean(field.required) || Object.values(consumers).some((consumer) => Boolean(consumer?.required))
    if (!required) return false
    const fieldValue = Object.prototype.hasOwnProperty.call(lockedExternalContextValues, name)
      ? lockedExternalContextValues[name]
      : externalContextValues[name]
    return fieldValue === undefined || fieldValue === null || fieldValue === ''
  }).length
  const sessionFieldCount = externalContextFieldEntries.filter(([, field]) => field.scope === 'session').length
  const runFieldCount = externalContextFieldEntries.length - sessionFieldCount
  const lockedSessionFieldCount = externalContextFieldEntries.filter(
    ([name, field]) => field.scope === 'session' && Object.prototype.hasOwnProperty.call(lockedExternalContextValues, name),
  ).length

  useEffect(() => {
    if (!artifactPickerOpen || !artifactContext || !artifactScope) return
    let active = true
    setArtifactLoading(true)
    setArtifactLoadError(false)
    void listArtifacts(artifactScope, artifactContext.workspaceId, { directory: artifactDirectory, cursor: artifactCursor, limit: 100 })
      .then(page => { if (active) setArtifactPage(page) })
      .catch(() => { if (active) setArtifactLoadError(true) })
      .finally(() => { if (active) setArtifactLoading(false) })
    return () => { active = false }
  }, [artifactContext?.workspaceId, artifactCursor, artifactDirectory, artifactPickerOpen, artifactScope])

  const setInput = useCallback((next: string) => {
    if (value === undefined) setInternalInput(next)
    onChange?.(next)
  }, [onChange, value])

  const handleSend = useCallback(() => {
    if ((!input.trim() && selectedArtifacts.length === 0) || blocked) return
    if (selectedArtifacts.length && onSendArtifacts) onSendArtifacts(input.trim(), selectedArtifacts)
    else onSend(input.trim())
    setInput('')
    setSelectedArtifacts([])
    setArtifactPickerOpen(false)
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }, [blocked, input, onSend, onSendArtifacts, selectedArtifacts, setInput])

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  const handleInput = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    const next = event.target.value
    setInput(next)
    const mention = /(?:^|\s)@([^@\s]*)$/.exec(next)
    if (mention && artifactContext) setArtifactPickerOpen(true)
    else if (!mention) setArtifactPickerOpen(false)
    const element = event.target
    element.style.height = 'auto'
    element.style.height = `${element.scrollHeight}px`
  }

  const addArtifact = (file: ArtifactFile) => {
    if (!file.revision_id || !file.revision || file.kind !== 'file' || selectedArtifacts.length >= 16) return
    setSelectedArtifacts(current => current.some(item => item.ref.artifact_id === file.id && item.ref.revision_id === file.revision_id)
      ? current
      : [...current, { ref: { artifact_id: file.id, revision_id: file.revision_id! }, label: file.path, content_type: file.revision?.content_type }])
    setArtifactPickerOpen(false)
    const withoutMention = input.replace(/(?:^|\s)@[^@\s]*$/, '').trimEnd()
    setInput(withoutMention)
  }

  const uploadAttachment = async (candidate: NonNullable<typeof pendingAttachment>) => {
    if (!canWriteArtifacts || !artifactContext || !artifactScope) return
    const controller = new AbortController()
    uploadControllerRef.current = controller
    setArtifactError(null)
    setUploadingFile(true)
    try {
      const capabilities = await getArtifactCapabilities(artifactScope, controller.signal)
      controller.signal.throwIfAborted()
      const receipt = await uploadArtifactFile(
        artifactScope, artifactContext.workspaceId, candidate.file, candidate.path, capabilities,
        uploadedBytes => setPendingAttachment(current => current?.operationId === candidate.operationId
          ? { ...current, uploadedBytes }
          : current),
        candidate.operationId,
        controller.signal,
      )
      if (receipt.status !== 'committed' || !receipt.receipt) throw new Error('Upload did not return a committed Artifact revision')
      setSelectedArtifacts(current => [...current, {
        ref: receipt.receipt!, label: candidate.file.name, content_type: candidate.file.type || 'application/octet-stream',
      }])
      setPendingAttachment(null)
    } catch (cause) {
      setArtifactError(controller.signal.aborted
        ? 'Upload paused. Resume with the same file to reconcile the committed offset.'
        : cause instanceof Error ? cause.message : 'Artifact upload failed')
    } finally {
      if (uploadControllerRef.current === controller) uploadControllerRef.current = null
      setUploadingFile(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const startAttachmentUpload = (file?: File) => {
    if (!file || !canWriteArtifacts || !artifactContext || !artifactScope || pendingAttachment) return
    const name = file.name.replace(/[\\/\x00-\x1f]/g, '_').trim() || 'attachment'
    const candidate = { file, path: `attachments/${createUuid()}-${name}`, operationId: createUuid(), uploadedBytes: 0 }
    setPendingAttachment(candidate)
    void uploadAttachment(candidate)
  }

  const mentionQuery = /(?:^|\s)@([^@\s]*)$/.exec(input)?.[1]?.toLocaleLowerCase() ?? ''
  const artifactItems = (artifactPage?.items ?? []).filter(file => (file.kind === 'directory' || (file.kind === 'file' && file.revision_id))
    && file.path.toLocaleLowerCase().includes(mentionQuery))
  const parentDirectory = artifactDirectory.includes('/') ? artifactDirectory.slice(0, artifactDirectory.lastIndexOf('/')) : ''

  const resolvedStatus = runtimeBlocked
    ? runtimeBlockReason
    : isPreparing
      ? preparingText
      : isStopping
        ? 'Stopping...'
        : isSending
          ? statusText ?? 'Generating...'
          : statusText ?? 'Enter to send · Shift+Enter for new line'

  return (
    <div className={compact ? 'min-w-0 border-t border-border bg-surface/[0.78] p-ui-sm' : 'min-w-0 border-t border-border bg-surface/[0.78] p-ui-md'}>
      {externalContextFieldEntries.length > 0 ? (
        <div className="mb-ui-xs overflow-hidden rounded-control border border-border/80 bg-background/30">
          <div className="flex min-h-control items-stretch">
            <button
              type="button"
              onClick={() => setExternalContextOpen((current) => !current)}
              className="flex min-w-0 flex-1 flex-wrap items-center gap-ui-xs px-ui-sm text-left transition-colors hover:bg-control/35"
              aria-expanded={externalContextOpen}
            >
              {externalContextOpen
                ? <ChevronDown className="h-icon-sm w-icon-sm text-muted-foreground" />
                : <ChevronRight className="h-icon-sm w-icon-sm text-muted-foreground" />}
              <Braces className="h-icon-sm w-icon-sm text-primary-light" />
              <span className="font-mono text-system-control font-medium text-slate-100">External Context</span>
              <span className="font-mono text-product-caption text-muted-foreground">
                {externalContextFieldEntries.length} field{externalContextFieldEntries.length === 1 ? '' : 's'}
              </span>
              {missingRequiredExternalContextFields > 0 ? (
                <span className="ml-auto rounded-technical border border-amber-400/25 bg-amber-400/[0.06] px-ui-xs font-mono text-system-meta text-warning">
                  {missingRequiredExternalContextFields} required missing
                </span>
              ) : (
                <span className="ml-auto font-mono text-system-meta text-muted-foreground">
                  {sessionFieldCount > 0 ? `${lockedSessionFieldCount}/${sessionFieldCount} session fixed · ${runFieldCount} run` : 'per Run'}
                </span>
              )}
            </button>
            {hasExternalContextValues && onClearExternalContextValues ? (
              <button
                type="button"
                onClick={onClearExternalContextValues}
                disabled={blocked}
                className="border-l border-border/70 px-ui-sm font-sans text-system-meta text-muted-foreground transition-colors hover:bg-control/35 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Clear
              </button>
            ) : null}
          </div>
          {externalContextOpen ? (
            <div className="border-t border-border/70 px-ui-sm pb-ui-sm">
              <p className="py-ui-xs font-sans text-product-caption text-muted-foreground">
                Session fields are set once and reused automatically. Run fields may change on each Run.
              </p>
              <ContractValueForm
                contract={externalContextContract}
                values={externalContextValues}
                lockedValues={lockedExternalContextValues}
                disabled={blocked}
                density="compact"
                onChange={onExternalContextValuesChange ?? (() => undefined)}
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {missingRequiredExternalContextFields > 0 && <p className="mb-ui-sm font-sans text-chrome-label text-warning">{missingRequiredExternalContextFields} required context field{missingRequiredExternalContextFields === 1 ? ' is' : 's are'} missing. <button type="button" onClick={() => setExternalContextOpen(true)} className="min-h-control-xs underline underline-offset-2">Review External Context</button></p>}
      <input ref={fileInputRef} type="file" className="hidden" aria-label="Choose an Artifact attachment" disabled={!canWriteArtifacts || blocked} onChange={event => startAttachmentUpload(event.target.files?.[0])} />
      {pendingAttachment && <section className="mb-ui-xs grid gap-ui-xs rounded-control border border-border p-ui-sm" aria-label="Attachment upload">
        <div className="flex min-w-0 items-center justify-between gap-ui-sm">
          <span className="min-w-0 truncate font-mono text-system-meta">{uploadingFile ? 'Uploading' : 'Upload paused'} · {pendingAttachment.file.name}</span>
          {uploadingFile
            ? <Button type="button" variant="ghost" size="xs" onClick={() => uploadControllerRef.current?.abort()} aria-label="Cancel attachment upload">Cancel</Button>
            : <div className="flex shrink-0 gap-ui-xs">
              <Button type="button" variant="outline" size="xs" onClick={() => void uploadAttachment(pendingAttachment)}>Resume</Button>
              <Button type="button" variant="ghost" size="xs" onClick={() => { setPendingAttachment(null); setArtifactError(null) }}>Discard</Button>
            </div>}
        </div>
        <progress className="h-2 w-full accent-primary" max={Math.max(1, pendingAttachment.file.size)} value={pendingAttachment.uploadedBytes} aria-label="Attachment upload progress" />
        <span className="font-mono text-system-micro text-muted-foreground">{pendingAttachment.uploadedBytes.toLocaleString()} / {pendingAttachment.file.size.toLocaleString()} bytes</span>
      </section>}
      {selectedArtifacts.length > 0 && <div className="mb-ui-xs flex min-w-0 flex-wrap gap-ui-xs" aria-label="Selected Artifact references">
        {selectedArtifacts.map((artifact, index) => <span key={`${artifact.ref.artifact_id}:${artifact.ref.revision_id}`} className="inline-flex min-w-0 max-w-full items-center gap-ui-xs rounded-control border border-primary/25 bg-primary/[0.06] px-ui-xs py-ui-xs font-mono text-system-meta text-slate-100">
          <span className="max-w-[18rem] truncate" title={`${artifact.label} · ${artifact.ref.revision_id}`}>{artifact.label}</span>
          <button type="button" onClick={() => setSelectedArtifacts(current => current.filter((_, itemIndex) => itemIndex !== index))} disabled={blocked} aria-label={`Remove ${artifact.label}`} className="rounded-control p-0.5 hover:bg-control/50"><X className="h-icon-xs w-icon-xs" /></button>
        </span>)}
      </div>}
      {artifactPickerOpen && artifactContext && <div className="mb-ui-xs max-h-64 overflow-auto rounded-control border border-border bg-surface p-ui-xs shadow-lg" role="listbox" aria-label="Artifact Workspace references">
        <div className="flex items-center justify-between gap-ui-sm border-b border-border/70 px-ui-xs py-ui-xs">
          <div className="min-w-0"><span className="font-mono text-system-label">@ {artifactDirectory || 'Workspace files'}</span><span className="ml-ui-xs text-system-meta text-muted-foreground">Exact revisions</span></div>
          {artifactDirectory && <button type="button" onClick={() => { setArtifactDirectory(parentDirectory); setArtifactCursor(null) }} className="font-mono text-system-meta text-primary-light">Up</button>}
        </div>
        {artifactLoading ? <p role="status" className="px-ui-sm py-ui-md text-product-caption text-muted-foreground">Loading Workspace files…</p>
          : artifactLoadError ? <p role="alert" className="px-ui-sm py-ui-md text-product-caption text-warning">Workspace files are unavailable for this identity.</p>
            : artifactItems.length === 0 ? <p className="px-ui-sm py-ui-md text-product-caption text-muted-foreground">No matching files in this directory.</p>
              : artifactItems.map(file => file.kind === 'directory' ? <button key={file.id} type="button" role="option" onClick={() => { setArtifactDirectory(file.path); setArtifactCursor(null) }} className="flex min-h-control w-full items-center gap-ui-sm rounded-control px-ui-sm text-left font-mono text-system-label hover:bg-control/45"><FilePlus2 className="h-icon-sm w-icon-sm" />{file.path}</button>
                : <button key={`${file.id}:${file.revision_id}`} type="button" role="option" onClick={() => addArtifact(file)} disabled={selectedArtifacts.length >= 16} className="flex min-h-control w-full items-center justify-between gap-ui-sm rounded-control px-ui-sm text-left hover:bg-control/45 disabled:opacity-50"><span className="min-w-0 truncate font-mono text-system-label">{file.path}</span><span className="shrink-0 font-mono text-system-meta text-muted-foreground">rev {file.revision_id?.slice(0, 8)}</span></button>)}
        {artifactPage?.has_more && <button type="button" onClick={() => setArtifactCursor(artifactPage.next_cursor)} className="mt-ui-xs min-h-control w-full border-t border-border/70 px-ui-sm font-mono text-system-meta text-primary-light">Load more files</button>}
      </div>}
      {artifactError && <p role="alert" className="mb-ui-xs break-words font-sans text-product-caption text-warning">{artifactError}</p>}
      <div className="min-w-0 max-w-full rounded-container border border-control-border bg-surface transition-colors focus-within:border-primary-light focus-within:ring-1 focus-within:ring-primary-light">
        <textarea
          aria-label="Message"
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={runtimeBlocked ? (runtimeBlockReason ?? 'Runtime blocked') : placeholder}
          rows={1}
          className={compact
            ? 'min-h-control max-h-multiline min-w-0 w-full resize-none bg-transparent px-ui-sm py-ui-sm font-sans text-product-small text-slate-100 outline-none placeholder:text-muted-foreground'
            : 'min-h-control-row max-h-multiline min-w-0 w-full resize-none bg-transparent px-ui-md py-ui-sm font-sans text-product-reading text-slate-100 outline-none placeholder:text-muted-foreground'}
          disabled={blocked}
        />
        <div className={compact
          ? 'flex min-w-0 items-center justify-between gap-ui-xs border-t border-border/60 px-ui-xs py-ui-xs'
          : 'flex min-w-0 items-center justify-between border-t border-border/60 px-ui-sm py-ui-sm'}>
          <div className="flex min-w-0 items-center gap-ui-xs">
            {showUploadControl && <Button type="button" variant="ghost" size={compact ? 'xs' : 'sm'} disabled={!canWriteArtifacts || blocked} onClick={() => fileInputRef.current?.click()} title={artifactContext ? 'Upload a file into the active Artifact Workspace' : 'Select an Artifact Workspace in External Context first'} className="font-sans text-muted-foreground">
              <Paperclip className="h-icon-sm w-icon-sm" />
              Attach
            </Button>}
            <Button type="button" variant="ghost" size={compact ? 'xs' : 'sm'} disabled={!artifactContext || blocked} onClick={() => setArtifactPickerOpen(open => !open)} title={artifactContext ? 'Reference a revision from the active Artifact Workspace' : 'Select an Artifact Workspace in External Context first'} className="font-sans text-muted-foreground">
              <AtSign className="h-icon-sm w-icon-sm" />
              @ Files
            </Button>
            <Button type="button" variant="ghost" size={compact ? 'xs' : 'sm'} disabled title="Not available in this workspace" className="font-sans text-muted-foreground">
              <Wrench className="h-icon-sm w-icon-sm" />
              Tools
            </Button>
          </div>
          <div className="flex min-w-0 shrink-0 items-center gap-ui-sm">
            {compact ? <span className="sr-only">{uploadingFile ? 'Uploading attachment…' : resolvedStatus}</span> : (
              <span className="hidden max-w-[17.5rem] truncate font-mono text-system-micro text-muted-foreground sm:inline">
                {resolvedStatus}
              </span>
            )}
            {isSending ? (
              <Button
                type="button"
                variant="destructive"
                size={compact ? 'xs' : 'sm'}
                onClick={onStop}
                disabled={isStopping}
                aria-label={isStopping ? 'Stopping generation' : 'Stop generation'}
                className="w-control-sm px-0"
              >
                <Square className="h-icon-sm w-icon-sm fill-current" />
              </Button>
            ) : (
              <Button
                type="button"
                size={compact ? 'xs' : 'sm'}
                onClick={handleSend}
                disabled={(!input.trim() && selectedArtifacts.length === 0) || blocked}
                className="w-control-sm px-0"
                aria-label={isPreparing ? preparingText : 'Send message'}
              >
                {isPreparing || uploadingFile ? <Loader2 className="h-icon w-icon animate-spin" /> : <Send className="h-icon w-icon" />}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
