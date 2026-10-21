import { useMemo, useState, type FormEvent, type ChangeEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight, File, Folder, FolderPlus, Upload, X } from 'lucide-react'
import { Button, Input } from '@woobe/ui'
import { ResourcePage, ResourceToolbar } from '@/components/common/ResourcePage'
import { ApiError } from '@/lib/api/errors'
import { createUuid } from '@/lib/uuid'
import {
  useArtifactCapabilities,
  useArtifactWorkspace,
  useArtifacts,
  useCreateArtifactDirectory,
  useDeleteArtifact,
  useMoveArtifact,
} from '../hooks'
import { uploadArtifactFile } from '../upload'
import type { ArtifactEnvironment, ArtifactFile } from '../types'

const environments: ArtifactEnvironment[] = ['draft', 'staging', 'production']

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 403) {
    return 'The current Project and Artifact Workspace grants do not authorize this operation.'
  }
  return error instanceof Error ? error.message : 'Artifact operation failed.'
}

function originLabel(origin: string | undefined) {
  switch (origin) {
    case 'upload': return 'Uploaded original'
    case 'application': return 'Application output'
    case 'agent': return 'Agent output'
    case 'tool': return 'Tool output'
    case 'processing': return 'Processed derivative'
    case 'copy': return 'Copied representation'
    default: return 'No revision'
  }
}

function breadcrumbs(path: string) {
  if (!path) return []
  const parts = path.split('/')
  return parts.map((part, index) => ({ name: part, path: parts.slice(0, index + 1).join('/') }))
}

function childPath(directory: string, name: string) {
  return directory ? `${directory}/${name}` : name
}

function isDerived(item: ArtifactFile) {
  return item.revision?.origin === 'processing' || item.revision?.origin === 'copy'
}

export function ArtifactExplorer({
  projectId,
  workspaceId,
  environment,
  onEnvironmentChange,
}: {
  projectId: string
  workspaceId: string
  environment: ArtifactEnvironment
  onEnvironmentChange: (environment: ArtifactEnvironment) => void
}) {
  const { workspaceId: identityWorkspaceId } = useParams<{ workspaceId: string }>()
  const navigate = useNavigate()
  const [directory, setDirectory] = useState('')
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null])
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')
  const [showFolderForm, setShowFolderForm] = useState(false)
  const [folderError, setFolderError] = useState<string | null>(null)
  const [operationError, setOperationError] = useState<string | null>(null)
  const [operationNotice, setOperationNotice] = useState<string | null>(null)
  const [moving, setMoving] = useState<ArtifactFile | null>(null)
  const [deleting, setDeleting] = useState<ArtifactFile | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [pendingUpload, setPendingUpload] = useState<{
    file: File
    path: string
    operationId: string
    uploadedBytes: number
  } | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadBusy, setUploadBusy] = useState(false)
  const pageCursor = cursorStack[cursorStack.length - 1] ?? null
  const workspaceQuery = useArtifactWorkspace(projectId, environment, workspaceId)
  const capabilitiesQuery = useArtifactCapabilities(projectId, environment)
  const filesQuery = useArtifacts(projectId, environment, workspaceId, directory, pageCursor)
  const createFolder = useCreateArtifactDirectory(projectId, environment, workspaceId)
  const moveFile = useMoveArtifact(projectId, environment, workspaceId)
  const deleteFile = useDeleteArtifact(projectId, environment, workspaceId)
  const records = filesQuery.data?.items ?? []
  const sortedRecords = useMemo(() => [...records].sort((left, right) => {
    const order = left.path.localeCompare(right.path, undefined, { sensitivity: 'base' })
    return sortOrder === 'asc' ? order : -order
  }), [records, sortOrder])
  const originals = sortedRecords.filter(item => !isDerived(item))
  const derived = sortedRecords.filter(isDerived)
  const pathCrumbs = breadcrumbs(directory)

  async function submitFolder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const name = String(data.get('folder_name') ?? '').trim()
    if (!name || name.includes('/')) {
      setFolderError('Enter a single folder name without a slash.')
      return
    }
    setFolderError(null)
    setOperationError(null)
    try {
      await createFolder.mutateAsync({ path: childPath(directory, name), operationId: createUuid() })
      setShowFolderForm(false)
      setOperationNotice(`Folder “${name}” created.`)
    } catch (error) {
      setFolderError(errorMessage(error))
    }
  }

  async function submitMove(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!moving) return
    const data = new FormData(event.currentTarget)
    const path = String(data.get('path') ?? '').trim()
    if (!path) return
    setOperationError(null)
    try {
      await moveFile.mutateAsync({
        artifactId: moving.id, path, expectedVersion: moving.version, operationId: createUuid(),
      })
      setOperationNotice(`Moved “${moving.path}” to “${path}”.`)
      setMoving(null)
    } catch (error) {
      setOperationError(errorMessage(error))
    }
  }

  function closeMove() {
    const triggerId = moving ? `artifact-move-trigger-${moving.id}` : null
    setMoving(null)
    if (triggerId) requestAnimationFrame(() => document.getElementById(triggerId)?.focus())
  }

  async function confirmDelete() {
    if (!deleting) return
    setDeleteError(null)
    try {
      await deleteFile.mutateAsync({
        artifactId: deleting.id, expectedVersion: deleting.version, operationId: createUuid(),
      })
      setOperationNotice(`“${deleting.path}” was moved to the deleted state.`)
      setDeleting(null)
    } catch (error) {
      setDeleteError(errorMessage(error))
    }
  }

  async function executeUpload(candidate: NonNullable<typeof pendingUpload>) {
    const capabilities = capabilitiesQuery.data
    if (!capabilities) {
      setUploadError('Upload limits are unavailable. Retry after the capability request completes.')
      return
    }
    setUploadBusy(true)
    setUploadError(null)
    setOperationError(null)
    try {
      const result = await uploadArtifactFile(
        { projectId, environment }, workspaceId, candidate.file, candidate.path, capabilities,
        uploadedBytes => setPendingUpload(current => current?.operationId === candidate.operationId
          ? { ...current, uploadedBytes }
          : current),
        candidate.operationId,
      )
      if (result.status !== 'committed') throw new Error(`Upload ended in ${result.status}`)
      setOperationNotice(`Uploaded “${candidate.path}” as revision ${result.receipt?.revision_id ?? 'available'}.`)
      setPendingUpload(null)
      setUploadError(null)
    } catch (error) {
      setUploadError(`${errorMessage(error)} The upload operation is retained; retry with the same file to reconcile it.`)
    } finally {
      setUploadBusy(false)
    }
  }

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0]
    event.currentTarget.value = ''
    if (!file) return
    const candidate = {
      file,
      path: childPath(directory, file.name),
      operationId: createUuid(),
      uploadedBytes: 0,
    }
    setPendingUpload(candidate)
    void executeUpload(candidate)
  }

  if (workspaceQuery.isPending) {
    return <ResourcePage title="Artifact Workspace" description="Loading authorized Workspace metadata…"><p role="status">Loading Workspace…</p></ResourcePage>
  }
  if (workspaceQuery.isError) {
    return <ResourcePage title="Artifact Workspace" description="The selected Workspace could not be opened."><div role="alert" className="grid gap-ui-sm rounded-technical border border-error/40 p-ui-lg"><p>{errorMessage(workspaceQuery.error)}</p><Button type="button" variant="outline" onClick={() => navigate(`/workspaces/${identityWorkspaceId}/projects/${projectId}/artifacts?environment=${environment}`)}>Back to Workspaces</Button></div></ResourcePage>
  }
  const workspace = workspaceQuery.data

  function renderFile(item: ArtifactFile) {
    const folder = item.kind === 'directory'
    const revision = item.revision
    const displayName = item.path.split('/').slice(-1)[0] ?? item.path
    return (
      <article key={item.id} className="grid min-w-0 gap-ui-md rounded-container border border-border bg-card p-ui-md lg:grid-cols-[minmax(0,1fr)_minmax(13rem,0.7fr)_auto] lg:items-center">
        <div className="flex min-w-0 items-start gap-ui-sm">
          {folder ? <Folder aria-hidden="true" className="mt-ui-xs h-icon w-icon shrink-0 text-primary-light" /> : <File aria-hidden="true" className="mt-ui-xs h-icon w-icon shrink-0 text-muted-foreground" />}
          <div className="min-w-0">
            {folder ? (
              <button type="button" className="max-w-full break-all text-left font-medium underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" onClick={() => { setDirectory(item.path); setCursorStack([null]); setOperationNotice(null) }}>
                {displayName}
              </button>
            ) : <p className="break-all font-medium">{displayName}</p>}
            <p className="mt-ui-xs text-product-small text-muted-foreground">{folder ? 'Directory' : revision?.content_type ?? 'File without a committed revision'}</p>
          </div>
            {!folder && revision && <button type="button" className="mt-ui-xs text-product-small font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" onClick={() => navigate(`/workspaces/${identityWorkspaceId}/projects/${projectId}/artifacts/${encodeURIComponent(workspaceId)}/files/${encodeURIComponent(item.id)}/revisions/${encodeURIComponent(revision.id)}?environment=${environment}`)}>Open document reader</button>}
        </div>
        <dl className="grid min-w-0 grid-cols-2 gap-x-ui-sm gap-y-ui-xs text-product-small sm:grid-cols-3 lg:grid-cols-2">
          <div className="min-w-0"><dt className="text-muted-foreground">Revision</dt><dd className="break-all font-mono">{revision?.id ?? '—'} · v{item.version}</dd></div>
          <div className="min-w-0"><dt className="text-muted-foreground">Size</dt><dd>{revision ? `${revision.size_bytes.toLocaleString()} bytes` : '—'}</dd></div>
          <div className="min-w-0"><dt className="text-muted-foreground">Origin</dt><dd>{originLabel(revision?.origin)}</dd></div>
          <div className="min-w-0"><dt className="text-muted-foreground">Processing</dt><dd>{revision?.origin === 'processing' ? 'Derived output' : folder ? 'Not applicable' : 'No job state in this listing'}</dd></div>
        </dl>
        <div className="flex flex-wrap gap-ui-xs">
          {!folder && <Button id={`artifact-move-trigger-${item.id}`} type="button" size="sm" variant="outline" onClick={() => { setMoving(item); setOperationError(null) }}>Move / rename</Button>}
          <Button type="button" size="sm" variant="outline" onClick={() => { setDeleting(item); setDeleteError(null) }}>Delete</Button>
        </div>
      </article>
    )
  }

  return (
    <ResourcePage
      title={workspace.name}
      description="Browse immediate directory contents. File metadata, immutable revisions and derived representations remain separate."
      action={(
        <Button type="button" variant="outline" onClick={() => navigate(`/workspaces/${identityWorkspaceId}/projects/${projectId}/artifacts?environment=${environment}`)}>
          <ArrowLeft className="h-icon w-icon" /> Workspaces
        </Button>
      )}
    >
      <section className="grid min-w-0 gap-ui-md rounded-technical border border-border bg-card p-ui-md md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
        <div className="min-w-0">
          <p className="text-product-small text-muted-foreground">
            Environment <span className="font-medium text-foreground">{environment}</span>
            {' · '}Status <span className="font-medium text-foreground">{workspace.status}</span>
            {' · '}Storage <span className="font-medium text-foreground">{workspace.used_bytes.toLocaleString()} / {workspace.quota_bytes.toLocaleString()} bytes</span>
            {workspace.reserved_bytes > 0 && <> · {workspace.reserved_bytes.toLocaleString()} reserved</>}
          </p>
          <details className="mt-ui-sm text-product-small">
            <summary className="w-fit cursor-pointer text-muted-foreground">External identity and storage details</summary>
            <dl className="mt-ui-sm grid min-w-0 gap-x-ui-lg gap-y-ui-xs sm:grid-cols-2 lg:grid-cols-4">
              <div className="min-w-0"><dt className="text-muted-foreground">Namespace</dt><dd className="break-all font-mono">{workspace.external_namespace}</dd></div>
              <div className="min-w-0"><dt className="text-muted-foreground">External key</dt><dd className="break-all font-mono">{workspace.external_key}</dd></div>
              <div><dt className="text-muted-foreground">Storage profile</dt><dd>{workspace.storage_profile}</dd></div>
              <div><dt className="text-muted-foreground">Retention</dt><dd>{workspace.retention_days} days</dd></div>
            </dl>
          </details>
        </div>
        <label className="grid gap-ui-xs text-product-small font-medium" htmlFor="artifact-environment">
          Environment
          <select id="artifact-environment" value={environment} onChange={event => onEnvironmentChange(event.target.value as ArtifactEnvironment)} className="h-control rounded-control border border-input bg-background px-ui-sm text-product-small">
            {environments.map(value => <option key={value} value={value}>{value[0]?.toUpperCase()}{value.slice(1)}</option>)}
          </select>
        </label>
      </section>

      <ResourceToolbar className="flex-wrap">
        <Button type="button" variant="outline" onClick={() => { setShowFolderForm(value => !value); setFolderError(null) }} disabled={createFolder.isPending}>
          <FolderPlus className="h-icon w-icon" /> New folder
        </Button>
        <label className="inline-flex h-control cursor-pointer items-center gap-ui-xs rounded-control border border-border px-ui-sm text-product-small font-medium hover:bg-muted/40 focus-within:ring-2 focus-within:ring-primary" htmlFor="artifact-file-upload">
          <Upload className="h-icon w-icon" /> Upload file
          <input id="artifact-file-upload" type="file" className="sr-only" disabled={!capabilitiesQuery.data || uploadBusy || Boolean(pendingUpload)} onChange={selectFile} />
        </label>
        {capabilitiesQuery.isError && <span role="status" className="text-product-small text-muted-foreground">Upload limits are unavailable.</span>}
        <label className="ml-auto inline-flex items-center gap-ui-sm text-product-small" htmlFor="artifact-sort">
          Sort this page
          <select id="artifact-sort" value={sortOrder} onChange={event => setSortOrder(event.target.value as 'asc' | 'desc')} className="h-control rounded-control border border-input bg-background px-ui-sm">
            <option value="asc">Name A–Z</option><option value="desc">Name Z–A</option>
          </select>
        </label>
      </ResourceToolbar>

      {showFolderForm && (
        <form onSubmit={event => void submitFolder(event)} className="flex flex-wrap items-end gap-ui-sm rounded-technical border border-border p-ui-md">
          <label className="grid min-w-0 flex-1 gap-ui-xs text-product-small font-medium" htmlFor="artifact-folder-name">Folder name<Input id="artifact-folder-name" name="folder_name" required maxLength={255} autoFocus /></label>
          <Button type="submit" disabled={createFolder.isPending}>{createFolder.isPending ? 'Creating…' : 'Create folder'}</Button>
          <Button type="button" variant="outline" onClick={() => setShowFolderForm(false)}>Cancel</Button>
          {folderError && <p role="alert" className="basis-full text-product-small text-error">{folderError}</p>}
        </form>
      )}

      {pathCrumbs.length > 0 && (
        <nav aria-label="Artifact path" className="flex min-w-0 flex-wrap items-center gap-ui-xs text-product-small">
          <button type="button" onClick={() => { setDirectory(''); setCursorStack([null]) }} className="font-medium underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">Root</button>
          {pathCrumbs.map(crumb => <span key={crumb.path} className="flex min-w-0 items-center gap-ui-xs"><span aria-hidden="true">/</span><button type="button" className="max-w-full break-all text-left underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" onClick={() => { setDirectory(crumb.path); setCursorStack([null]) }}>{crumb.name}</button></span>)}
        </nav>
      )}

      {operationNotice && <p role="status" className="rounded-technical border border-primary/30 bg-primary/5 p-ui-sm text-product-small">{operationNotice}</p>}
      {operationError && <p role="alert" className="rounded-technical border border-error/40 p-ui-sm text-product-small text-error">{operationError}</p>}
      {uploadError && <p role="alert" className="rounded-technical border border-error/40 p-ui-sm text-product-small text-error">{uploadError}</p>}
      {pendingUpload && (
        <section className="grid gap-ui-sm rounded-technical border border-border p-ui-md" aria-label="Upload progress">
          <div className="flex min-w-0 items-center justify-between gap-ui-sm">
            <p className="min-w-0 break-all text-product-small font-medium">{uploadBusy ? 'Uploading' : 'Upload needs attention'} · {pendingUpload.file.name}</p>
            <button type="button" aria-label="Dismiss upload" disabled={uploadBusy} onClick={() => { setPendingUpload(null); setUploadError(null) }} className="rounded-control p-ui-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"><X className="h-icon w-icon" /></button>
          </div>
          <progress className="h-2 w-full accent-primary" max={Math.max(1, pendingUpload.file.size)} value={pendingUpload.uploadedBytes} aria-label="Upload progress" />
          <p className="text-product-small text-muted-foreground">{pendingUpload.uploadedBytes.toLocaleString()} / {pendingUpload.file.size.toLocaleString()} bytes · {capabilitiesQuery.data?.max_upload_part_bytes.toLocaleString() ?? '—'} bytes per part</p>
          {!uploadBusy && uploadError && <Button type="button" variant="outline" className="w-fit" onClick={() => void executeUpload(pendingUpload)}>Retry same upload</Button>}
        </section>
      )}

      {filesQuery.isPending ? (
        <p role="status" className="rounded-technical border border-border p-ui-lg">Loading this directory…</p>
      ) : filesQuery.isError ? (
        <div role="alert" className="grid gap-ui-sm rounded-technical border border-error/40 p-ui-lg"><p>{errorMessage(filesQuery.error)}</p><Button type="button" variant="outline" className="w-fit" onClick={() => void filesQuery.refetch()}>Retry</Button></div>
      ) : records.length === 0 ? (
        <div className="rounded-technical border border-dashed border-border p-ui-xl text-center">
          <p className="font-medium">This directory is empty</p>
          <p className="mt-ui-xs text-product-small text-muted-foreground">Upload a file or create a folder. Access is checked by the server for every operation.</p>
        </div>
      ) : (
        <div className="grid min-w-0 gap-ui-lg">
          {filesQuery.data.truncated && <p role="status" className="text-product-small text-warning">The current result is partial; browse pages to continue.</p>}
          {originals.length > 0 && <section aria-labelledby="artifact-originals-heading" className="grid min-w-0 gap-ui-sm"><h2 id="artifact-originals-heading" className="font-medium">Files and folders</h2>{originals.map(renderFile)}</section>}
          {derived.length > 0 && <section aria-labelledby="artifact-derived-heading" className="grid min-w-0 gap-ui-sm"><h2 id="artifact-derived-heading" className="font-medium">Representations and derived files</h2>{derived.map(renderFile)}</section>}
        </div>
      )}

      {filesQuery.data && (cursorStack.length > 1 || filesQuery.data.has_more) && (
        <ResourceToolbar className="justify-end">
          <Button type="button" variant="outline" disabled={cursorStack.length <= 1 || filesQuery.isFetching} onClick={() => setCursorStack(stack => stack.slice(0, -1))}><ChevronLeft className="h-icon w-icon" /> Previous</Button>
          <Button type="button" variant="outline" disabled={!filesQuery.data.has_more || !filesQuery.data.next_cursor || filesQuery.isFetching} onClick={() => { if (filesQuery.data?.next_cursor) setCursorStack(stack => [...stack, filesQuery.data!.next_cursor]) }}>Next <ChevronRight className="h-icon w-icon" /></Button>
        </ResourceToolbar>
      )}

      {moving && (
        <form onSubmit={event => void submitMove(event)} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); closeMove() } }} className="fixed inset-0 z-modal grid place-items-center bg-black/70 p-ui-sm" aria-labelledby="artifact-move-title" role="dialog" aria-modal="true">
          <div className="grid w-full max-w-dialog gap-ui-md rounded-container border border-border bg-surface p-ui-lg shadow-popup">
            <div className="flex items-start justify-between gap-ui-sm"><div><h2 id="artifact-move-title" className="font-medium">Move or rename</h2><p className="mt-ui-xs break-all text-product-small text-muted-foreground">{moving.path}</p></div><button type="button" aria-label="Close move dialog" onClick={closeMove} className="rounded-control p-ui-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"><X className="h-icon w-icon" /></button></div>
            <label className="grid gap-ui-xs text-product-small font-medium" htmlFor="artifact-new-path">New full path<Input id="artifact-new-path" name="path" required maxLength={1024} defaultValue={moving.path} autoFocus /></label>
            <p className="text-product-small text-muted-foreground">The server compares version {moving.version} before changing the path.</p>
            {operationError && <p role="alert" className="text-product-small text-error">{operationError}</p>}
            <div className="flex flex-wrap justify-end gap-ui-sm"><Button type="button" variant="outline" onClick={closeMove}>Cancel</Button><Button type="submit" disabled={moveFile.isPending}>{moveFile.isPending ? 'Saving…' : 'Save path'}</Button></div>
          </div>
        </form>
      )}

      {deleting && (
        <section className="grid gap-ui-sm rounded-technical border border-error/40 p-ui-md" aria-label="Confirm deletion">
          <p className="break-all text-product-small">Delete “{deleting.path}”? This is a version-checked logical deletion.</p>
          {deleteError && <p role="alert" className="text-product-small text-error">{deleteError}</p>}
          <div className="flex flex-wrap gap-ui-sm"><Button type="button" variant="outline" onClick={() => setDeleting(null)}>Cancel</Button><Button type="button" variant="destructive" disabled={deleteFile.isPending} onClick={() => void confirmDelete()}>{deleteFile.isPending ? 'Deleting…' : 'Confirm delete'}</Button></div>
        </section>
      )}

      <p className="text-system-meta text-muted-foreground">Rows are authorized server-side against the current Project, Environment and Workspace grant. This listing does not include processing-job state.</p>
    </ResourcePage>
  )
}
