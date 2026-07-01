import { useEffect, useMemo, useRef, useState } from 'react'
import { useUploadDocumentFile } from '@/features/knowledge/hooks'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { CheckCircle2, FileText, FolderOpen, Search, UploadCloud, X } from 'lucide-react'
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

function collectionFallbackName(id: string): string {
  return id.slice(0, 8)
}

export function UploadDocumentModal({ open, onClose, projectId, collectionIds, defaultCollectionId }: UploadDocumentModalProps) {
  const uploadDocument = useUploadDocumentFile()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [collectionId, setCollectionId] = useState(defaultCollectionId || '')
  const [collectionQuery, setCollectionQuery] = useState('')
  const [title, setTitle] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const collectionKey = collectionIds.map((collection) => collection.id).join('|')

  useEffect(() => {
    if (!open) return
    setCollectionId(defaultCollectionId || collectionIds[0]?.id || '')
    setCollectionQuery('')
    setTitle('')
    setFile(null)
    setIsDragging(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [open, defaultCollectionId, collectionKey])

  const selectedCollection = useMemo(
    () => collectionIds.find((collection) => collection.id === collectionId),
    [collectionIds, collectionId],
  )

  const filteredCollections = useMemo(() => {
    const query = collectionQuery.trim().toLowerCase()
    if (!query) return collectionIds
    return collectionIds.filter((collection) => {
      const name = collection.name || collectionFallbackName(collection.id)
      return name.toLowerCase().includes(query) || collection.id.toLowerCase().includes(query)
    })
  }, [collectionIds, collectionQuery])

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

  const openNativeFilePicker = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setValidatedFile(event.target.files?.[0] ?? null)
    event.target.value = ''
  }

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()
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
    <Dialog open={open} onClose={onClose} title="Upload Document" className="max-w-2xl">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid gap-4 md:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-3">
            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <label className="text-xs font-medium uppercase tracking-wider text-muted">Destination collection</label>
                {selectedCollection && (
                  <span className="max-w-[220px] truncate rounded-full border border-border bg-background px-2 py-0.5 text-[11px] text-muted">
                    {selectedCollection.name || collectionFallbackName(selectedCollection.id)}
                  </span>
                )}
              </div>

              {collectionIds.length === 0 ? (
                <div className="rounded-xl border border-border bg-background p-4 text-sm text-muted">
                  No collections available. Create or attach a collection first.
                </div>
              ) : (
                <div className="rounded-xl border border-border bg-background/70 p-2">
                  <div className="relative mb-2">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
                    <input
                      value={collectionQuery}
                      onChange={(event) => setCollectionQuery(event.target.value)}
                      placeholder="Search collections"
                      className="h-9 w-full rounded-lg border border-border bg-surface pl-8 pr-3 text-sm outline-none transition-colors placeholder:text-muted focus:border-primary"
                    />
                  </div>

                  <ScrollArea className="max-h-56 pr-1">
                    <div className="space-y-1">
                      {filteredCollections.length === 0 ? (
                        <div className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted">
                          No collections match this search.
                        </div>
                      ) : (
                        filteredCollections.map((collection) => {
                          const selected = collection.id === collectionId
                          const name = collection.name || collectionFallbackName(collection.id)
                          return (
                            <button
                              key={collection.id}
                              type="button"
                              onClick={() => setCollectionId(collection.id)}
                              className={`flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors ${
                                selected
                                  ? 'border-primary bg-primary/10 text-white'
                                  : 'border-transparent bg-transparent text-muted hover:border-border hover:bg-surface hover:text-white'
                              }`}
                            >
                              <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${selected ? 'border-primary/40 bg-primary/15 text-primary' : 'border-border bg-background text-muted'}`}>
                                <FolderOpen className="h-4 w-4" />
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="truncate text-sm font-medium">{name}</p>
                                <p className="truncate text-[11px] text-muted">{collection.id}</p>
                              </div>
                              {selected && <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" />}
                            </button>
                          )
                        })
                      )}
                    </div>
                  </ScrollArea>
                </div>
              )}
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <label className="mb-2 block text-xs font-medium uppercase tracking-wider text-muted">File</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf"
                onChange={handleFileChange}
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
                onDrop={handleDrop}
                className={`rounded-xl border-2 border-dashed p-5 text-center outline-none transition-colors cursor-pointer ${
                  isDragging ? 'border-primary bg-primary/10' : 'border-border bg-background/70 hover:border-primary/60 hover:bg-background'
                }`}
              >
                <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-surface">
                  <UploadCloud className="h-5 w-5 text-primary" />
                </div>
                <p className="text-sm font-medium text-white">Drop file here</p>
                <p className="mt-1 text-xs text-muted">or click to browse from your computer</p>
                <div className="mt-4 flex flex-wrap justify-center gap-1.5">
                  {ACCEPTED_EXTENSIONS.map((extension) => (
                    <span key={extension} className="rounded-full border border-border bg-surface px-2 py-0.5 text-[11px] text-muted">
                      {extension.toUpperCase().replace('.', '')}
                    </span>
                  ))}
                </div>
                <p className="mt-3 text-[11px] text-muted">Maximum {MAX_FILE_MB} MB</p>
              </div>
            </div>

            {file && (
              <div className="rounded-xl border border-border bg-background p-3 flex items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-primary">
                  <FileText className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-white truncate">{file.name}</p>
                  <p className="text-xs text-muted mt-1">
                    {formatBytes(file.size)}{selectedCollection ? ` · ${selectedCollection.name || collectionFallbackName(selectedCollection.id)}` : ''}
                  </p>
                </div>
                <button
                  type="button"
                  className="rounded-md p-1 text-muted hover:text-white hover:bg-accent"
                  onClick={() => setFile(null)}
                  aria-label="Remove selected file"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium uppercase tracking-wider text-muted">Document title</label>
          <Input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Optional. Defaults to the file name."
          />
        </div>

        <div className="rounded-xl border border-border bg-background/60 p-3 text-xs text-muted">
          Uploaded files are stored with the configured storage driver and registered as <span className="text-white">UPLOADED</span>. Parsing and indexing run in a later pipeline.
        </div>

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            disabled={collectionIds.length === 0 || !collectionId || !file}
            loading={uploadDocument.isPending}
          >
            Upload Document
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
