import { useEffect, useMemo, useRef, useState, type FormEvent, type MouseEvent } from 'react'
import { CheckCircle2, Database, FileText, UploadCloud, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import {
  ACCEPTED_DOCUMENT_EXTENSIONS,
  DOCUMENT_ACCEPT_ATTRIBUTE,
  MAX_DOCUMENT_FILE_MB,
  titleFromDocumentFileName,
  validateKnowledgeDocumentFile,
} from '@/features/knowledge/documentFormats'
import { useUploadDocumentFile } from '@/features/knowledge/hooks'
import { formatBytes } from '@/lib/formatters/bytes'

interface CollectionDocumentUploadPanelProps {
  projectId: string
  collection: { id: string; name: string }
  onCancel: () => void
  onUploaded: () => void
  showDestination?: boolean
}

export function CollectionDocumentUploadPanel({ projectId, collection, onCancel, onUploaded, showDestination = true }: CollectionDocumentUploadPanelProps) {
  const uploadDocument = useUploadDocumentFile()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [title, setTitle] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  useEffect(() => {
    setTitle('')
    setFile(null)
    setIsDragging(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [collection.id])

  const selectedCollectionName = useMemo(() => collection.name || collection.id.slice(0, 8), [collection])

  const setValidatedFile = (candidate: File | null) => {
    if (!candidate) return
    const error = validateKnowledgeDocumentFile(candidate)
    if (error) {
      toast.error(error)
      return
    }
    setFile(candidate)
    if (!title.trim()) setTitle(titleFromDocumentFileName(candidate.name))
  }

  const openNativeFilePicker = () => {
    fileInputRef.current?.click()
  }

  const clearSelectedFile = (event?: MouseEvent) => {
    event?.preventDefault()
    event?.stopPropagation()
    setFile(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleCancel = () => {
    if (uploadDocument.isPending) return
    setTitle('')
    setFile(null)
    setIsDragging(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
    onCancel()
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!projectId) {
      toast.error('Project is required')
      return
    }
    if (!file) {
      toast.error('Select a TXT, MD, PDF or DOCX file')
      return
    }

    try {
      await uploadDocument.mutateAsync({
        projectId,
        collectionId: collection.id,
        title: title.trim() || titleFromDocumentFileName(file.name),
        file,
      })
      toast.success('Document uploaded')
      setTitle('')
      setFile(null)
      setIsDragging(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
      onUploaded()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to upload document')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {showDestination ? (
        <div className="rounded-xl border border-border bg-background/70 p-3">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted">Destination collection</p>
          <div className="mt-2 flex min-w-0 items-center gap-3 rounded-lg border border-primary/25 bg-primary/10 p-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary-light">
              <Database className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">{selectedCollectionName}</p>
              <p className="truncate text-[11px] text-muted">{collection.id}</p>
            </div>
            <CheckCircle2 className="h-4 w-4 shrink-0 text-primary-light" />
          </div>
        </div>
      ) : null}

      <div>
        <label className="mb-2 block text-[11px] font-medium uppercase tracking-wider text-muted">File</label>
        <input
          ref={fileInputRef}
          type="file"
          accept={DOCUMENT_ACCEPT_ATTRIBUTE}
          onChange={(event) => {
            setValidatedFile(event.target.files?.[0] ?? null)
            event.target.value = ''
          }}
          className="hidden"
        />
        <div
          role="button"
          tabIndex={0}
          onClick={openNativeFilePicker}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              openNativeFilePicker()
            }
          }}
          onDragEnter={(event) => {
            event.preventDefault()
            event.stopPropagation()
            setIsDragging(true)
          }}
          onDragOver={(event) => {
            event.preventDefault()
            event.stopPropagation()
            setIsDragging(true)
          }}
          onDragLeave={(event) => {
            event.preventDefault()
            event.stopPropagation()
            setIsDragging(false)
          }}
          onDrop={(event) => {
            event.preventDefault()
            event.stopPropagation()
            setIsDragging(false)
            setValidatedFile(event.dataTransfer.files?.[0] ?? null)
          }}
          className={`flex min-h-[210px] min-w-0 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-5 text-center outline-none transition-colors ${
            isDragging ? 'border-primary bg-primary/10' : 'border-border bg-background/70 hover:border-primary/60 hover:bg-background'
          }`}
        >
          {file ? (
            <div className="flex w-full max-w-full flex-col items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-surface text-primary-light">
                <FileText className="h-5 w-5" />
              </div>
              <div className="w-full min-w-0 rounded-xl border border-border bg-surface/70 p-3 text-left">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-white">{file.name}</p>
                    <p className="mt-1 truncate text-xs text-muted">{formatBytes(file.size)} · {selectedCollectionName}</p>
                  </div>
                  <button type="button" className="shrink-0 rounded-md p-1 text-muted hover:bg-accent hover:text-white" onClick={clearSelectedFile} aria-label="Remove selected file">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
              <p className="text-[11px] text-muted">Click the area to replace the file.</p>
            </div>
          ) : (
            <>
              <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-surface">
                <UploadCloud className="h-5 w-5 text-primary-light" />
              </div>
              <p className="text-sm font-medium text-white">Drop file here</p>
              <p className="mt-1 text-xs text-muted">or click to browse from your computer</p>
              <div className="mt-4 flex flex-wrap justify-center gap-1.5">
                {ACCEPTED_DOCUMENT_EXTENSIONS.map((extension) => (
                  <span key={extension} className="rounded-full border border-border bg-surface px-2 py-0.5 text-[11px] text-muted">
                    {extension.toUpperCase().replace('.', '')}
                  </span>
                ))}
              </div>
              <p className="mt-3 text-[11px] text-muted">Maximum {MAX_DOCUMENT_FILE_MB} MB</p>
            </>
          )}
        </div>
      </div>

      <div>
        <label className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted">Document title</label>
        <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Optional. Defaults to the file name." />
      </div>

      <div className="rounded-xl border border-border bg-background/60 p-3 text-xs leading-5 text-muted">
        PDF files must contain selectable text. DOCX ingestion preserves text, headings, lists and tables; embedded images are not indexed. Vector generation remains a separate, versioned step.
      </div>

      <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
        <Button type="button" variant="outline" onClick={handleCancel} disabled={uploadDocument.isPending}>Cancel</Button>
        <Button type="submit" disabled={!file || !projectId} loading={uploadDocument.isPending}>Upload document</Button>
      </div>
    </form>
  )
}
