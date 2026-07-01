import { useEffect, useMemo, useState } from 'react'
import { useUploadDocumentFile } from '@/features/knowledge/hooks'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { FileText, Upload, X } from 'lucide-react'
import { toast } from 'sonner'

interface UploadDocumentModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  collectionIds: { id: string; name: string }[]
  defaultCollectionId?: string
}

const ACCEPTED_EXTENSIONS = ['.txt', '.md', '.pdf']
const ACCEPTED_MIME_TYPES = ['text/plain', 'text/markdown', 'text/x-markdown', 'application/pdf', 'application/octet-stream']
const MAX_FILE_MB = 25

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function extensionOf(fileName: string): string {
  const dotIndex = fileName.lastIndexOf('.')
  return dotIndex >= 0 ? fileName.slice(dotIndex).toLowerCase() : ''
}

function titleFromFileName(fileName: string): string {
  return fileName.replace(/\.[^/.]+$/, '')
}

export function UploadDocumentModal({ open, onClose, projectId, collectionIds, defaultCollectionId }: UploadDocumentModalProps) {
  const uploadDocument = useUploadDocumentFile()
  const [collectionId, setCollectionId] = useState(defaultCollectionId || '')
  const [title, setTitle] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  useEffect(() => {
    if (open) {
      setCollectionId(defaultCollectionId || collectionIds[0]?.id || '')
      setTitle('')
      setFile(null)
      setIsDragging(false)
    }
  }, [open, defaultCollectionId, collectionIds])

  const selectedCollectionName = useMemo(
    () => collectionIds.find((collection) => collection.id === collectionId)?.name,
    [collectionIds, collectionId],
  )

  const validateFile = (candidate: File): string | null => {
    const extension = extensionOf(candidate.name)
    if (!ACCEPTED_EXTENSIONS.includes(extension)) {
      return 'Only TXT, MD and PDF files are supported.'
    }
    if (candidate.type && !ACCEPTED_MIME_TYPES.includes(candidate.type)) {
      return `Invalid file type: ${candidate.type}`
    }
    if (candidate.size <= 0) {
      return 'File is empty.'
    }
    if (candidate.size > MAX_FILE_MB * 1024 * 1024) {
      return `File exceeds ${MAX_FILE_MB} MB.`
    }
    return null
  }

  const setValidatedFile = (candidate: File | null) => {
    if (!candidate) return
    const error = validateFile(candidate)
    if (error) {
      toast.error(error)
      return
    }
    setFile(candidate)
    if (!title.trim()) {
      setTitle(titleFromFileName(candidate.name))
    }
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setValidatedFile(event.target.files?.[0] ?? null)
    event.target.value = ''
  }

  const handleDrop = (event: React.DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    setIsDragging(false)
    setValidatedFile(event.dataTransfer.files?.[0] ?? null)
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!collectionId) {
      toast.error('Select a collection')
      return
    }
    if (!file) {
      toast.error('Select a TXT, MD or PDF file')
      return
    }

    try {
      await uploadDocument.mutateAsync({
        projectId,
        collectionId,
        title: title.trim() || titleFromFileName(file.name),
        file,
      })
      toast.success('Document uploaded')
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to upload document')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Upload Document">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="rounded-lg border border-border bg-background/60 p-3">
          <p className="text-xs font-medium text-white">Supported files</p>
          <p className="mt-1 text-xs text-muted">TXT, Markdown and PDF. Maximum {MAX_FILE_MB} MB per file.</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-muted mb-1">Collection</label>
          {collectionIds.length === 0 ? (
            <p className="text-sm text-muted">No collections available. Create one first.</p>
          ) : (
            <Select
              value={collectionId}
              onChange={(event) => setCollectionId(event.target.value)}
              options={collectionIds.map((collection) => ({ value: collection.id, label: collection.name }))}
              placeholder="Select collection"
            />
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-muted mb-1">Title</label>
          <Input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Optional document title"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-muted mb-1">File</label>
          <label
            htmlFor="document-upload-file"
            className={`block rounded-xl border-2 border-dashed p-6 text-center transition-colors cursor-pointer ${
              isDragging ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
            }`}
            onDragOver={(event) => {
              event.preventDefault()
              setIsDragging(true)
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
          >
            <input
              type="file"
              accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf"
              onChange={handleFileChange}
              className="hidden"
              id="document-upload-file"
            />
            <Upload className="mx-auto h-8 w-8 text-muted mb-2" />
            <p className="text-sm text-white">Drop a file here or click to browse</p>
            <p className="mt-1 text-xs text-muted">The file will be stored in the configured ProjectRAI storage driver.</p>
          </label>
        </div>

        {file && (
          <div className="rounded-lg border border-border bg-background p-3 flex items-start gap-3">
            <FileText className="h-5 w-5 text-primary shrink-0 mt-0.5" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-white truncate">{file.name}</p>
              <p className="text-xs text-muted mt-1">
                {formatBytes(file.size)}{selectedCollectionName ? ` · ${selectedCollectionName}` : ''}
              </p>
            </div>
            <button
              type="button"
              className="rounded-md p-1 text-muted hover:text-white hover:bg-accent"
              onClick={() => setFile(null)}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            disabled={collectionIds.length === 0 || !file}
            loading={uploadDocument.isPending}
          >
            Upload
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
