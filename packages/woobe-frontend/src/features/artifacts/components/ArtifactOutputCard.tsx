import { useEffect, useState } from 'react'
import { Download, Eye, FileText, Loader2 } from 'lucide-react'
import { Button } from '@woobe/ui'
import { Link } from 'react-router-dom'
import { downloadArtifact } from '../api'
import type { ArtifactEnvironment } from '../types'
import type { ArtifactOutputInfo } from '@/features/playground/types'

interface Props {
  output: ArtifactOutputInfo
  projectId: string
  environment: ArtifactEnvironment
  workspaceId: string
  accountWorkspaceId?: string
}

const PREVIEW_LIMIT = 8 * 1024 * 1024

export function ArtifactOutputCard({ output, projectId, environment, workspaceId, accountWorkspaceId }: Props) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isPreviewable = /^(image\/(png|jpeg|webp|gif))$/i.test(output.content_type)
    && output.size_bytes <= PREVIEW_LIMIT

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  async function fetchContent() {
    setBusy(true)
    setError(null)
    try {
      return await downloadArtifact({ projectId, environment }, workspaceId, output.ref.artifact_id, output.ref.revision_id)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Artifact download failed')
      return null
    } finally {
      setBusy(false)
    }
  }

  async function preview() {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
      setPreviewUrl(null)
      return
    }
    const blob = await fetchContent()
    if (blob) setPreviewUrl(URL.createObjectURL(blob))
  }

  async function download() {
    const blob = await fetchContent()
    if (!blob) return
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = output.path.split('/').pop() || 'artifact'
    anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return (
    <article className="min-w-0 rounded-control border border-border/80 bg-background/45 p-ui-sm" aria-label={`Generated artifact ${output.path}`}>
      <div className="flex min-w-0 items-center gap-ui-sm">
        <FileText className="h-icon-sm w-icon-sm shrink-0 text-primary-light" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-system-label text-slate-100" title={output.path}>{output.path}</p>
          <p className="font-mono text-system-meta text-muted-foreground">{output.content_type} · {output.size_bytes.toLocaleString()} bytes · revision {output.ref.revision_id}</p>
        </div>
        {isPreviewable && <Button type="button" size="xs" variant="ghost" disabled={busy} onClick={() => void preview()} aria-label={previewUrl ? 'Hide image preview' : 'Preview generated image'}>
          {busy ? <Loader2 className="h-icon-sm w-icon-sm animate-spin" /> : <Eye className="h-icon-sm w-icon-sm" />}
        </Button>}
        <Button type="button" size="xs" variant="ghost" disabled={busy} onClick={() => void download()} aria-label={`Download ${output.path}`}>
          {busy ? <Loader2 className="h-icon-sm w-icon-sm animate-spin" /> : <Download className="h-icon-sm w-icon-sm" />}
        </Button>
      </div>
      {previewUrl && <img src={previewUrl} alt={`Preview of ${output.path}`} className="mt-ui-sm max-h-[24rem] max-w-full rounded-control object-contain" />}
      {output.source_refs.length > 0 && <ul className="mt-ui-xs flex min-w-0 flex-wrap gap-ui-xs" aria-label="Exact source citations">
        {output.source_refs.map((source, index) => <li key={`${source.artifact_id}:${source.revision_id}:${source.node_id ?? index}`}>
          {accountWorkspaceId ? <Link className="break-all rounded-control border border-border px-ui-xs py-ui-xs font-mono text-system-meta text-primary-light underline-offset-2 hover:underline" to={`/workspaces/${accountWorkspaceId}/projects/${projectId}/artifacts/${encodeURIComponent(workspaceId)}/files/${encodeURIComponent(source.artifact_id)}/revisions/${encodeURIComponent(source.revision_id)}?environment=${environment}`}>Source {index + 1} · rev {source.revision_id.slice(0, 8)}</Link>
            : <span className="break-all font-mono text-system-meta text-muted-foreground">Source {index + 1} · rev {source.revision_id.slice(0, 8)}</span>}
        </li>)}
      </ul>}
      {error && <p role="alert" className="mt-ui-xs break-words font-sans text-product-caption text-warning">{error}</p>}
    </article>
  )
}
