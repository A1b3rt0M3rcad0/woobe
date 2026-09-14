import { useEffect, useMemo, useRef, useState, type FormEvent, type MouseEvent } from 'react'
import { CheckCircle2, Database, FileText, UploadCloud, X } from 'lucide-react'
import { toast } from 'sonner'
import {
  Alert,
  AlertDescription,
  Badge,
  Button,
  Field,
  FieldDescription,
  FieldLabel,
  Input,
  SectionBlock,
  TechnicalListItem,
} from '@woobe/ui'

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

export function CollectionDocumentUploadPanel({
  projectId,
  collection,
  onCancel,
  onUploaded,
  showDestination = true,
}: CollectionDocumentUploadPanelProps) {
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

  const openNativeFilePicker = () => fileInputRef.current?.click()

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
    <form onSubmit={handleSubmit} className="grid gap-ui-md">
      {showDestination ? (
        <SectionBlock title="Destination collection" density="compact">
          <TechnicalListItem
            label={selectedCollectionName}
            description={collection.id}
            leading={(
              <span className="flex h-control-sm w-control-sm items-center justify-center rounded-control border border-primary/25 bg-primary/[0.08] text-primary-light">
                <Database className="h-icon w-icon" />
              </span>
            )}
            trailing={<CheckCircle2 className="h-icon w-icon text-primary-light" />}
          />
        </SectionBlock>
      ) : null}

      <Field>
        <FieldLabel>File</FieldLabel>
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
          className={`flex min-h-52 min-w-0 cursor-pointer flex-col items-center justify-center rounded-container border border-dashed p-ui-lg text-center outline-none transition-colors focus-visible:ring-1 focus-visible:ring-primary/40 ${
            isDragging ? 'border-primary/45 bg-primary/[0.08]' : 'border-border bg-background/35 hover:border-primary/30 hover:bg-control/25'
          }`}
        >
          {file ? (
            <div className="grid w-full max-w-full justify-items-center gap-ui-md">
              <span className="flex h-control-lg w-control-lg items-center justify-center rounded-control border border-border bg-control text-primary-light">
                <FileText className="h-icon-lg w-icon-lg" />
              </span>
              <TechnicalListItem
                className="w-full text-left"
                label={file.name}
                description={`${formatBytes(file.size)} · ${selectedCollectionName}`}
                trailing={(
                  <Button type="button" size="iconSm" variant="ghost" onClick={clearSelectedFile} aria-label="Remove selected file">
                    <X className="h-icon w-icon" />
                  </Button>
                )}
              />
              <p className="font-sans text-product-caption text-muted-foreground">Click the area to replace the file.</p>
            </div>
          ) : (
            <div className="grid justify-items-center gap-ui-sm">
              <span className="flex h-control-lg w-control-lg items-center justify-center rounded-control border border-border bg-control text-primary-light">
                <UploadCloud className="h-icon-lg w-icon-lg" />
              </span>
              <div>
                <p className="font-mono text-system-control font-semibold text-accent-foreground">Drop file here</p>
                <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">or click to browse from your computer</p>
              </div>
              <div className="flex flex-wrap justify-center gap-ui-xs">
                {ACCEPTED_DOCUMENT_EXTENSIONS.map((extension) => (
                  <Badge key={extension} variant="outline" size="compact">
                    {extension.toUpperCase().replace('.', '')}
                  </Badge>
                ))}
              </div>
              <FieldDescription>Maximum {MAX_DOCUMENT_FILE_MB} MB</FieldDescription>
            </div>
          )}
        </div>
      </Field>

      <Field>
        <FieldLabel>Document title</FieldLabel>
        <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Optional. Defaults to the file name." />
      </Field>

      <Alert variant="info">
        <AlertDescription>
          PDF files must contain selectable text. DOCX ingestion preserves text, headings, lists and tables; embedded images are not indexed. Vector generation remains a separate, versioned step.
        </AlertDescription>
      </Alert>

      <div className="flex flex-col-reverse gap-ui-sm border-t border-border pt-ui-md sm:flex-row sm:justify-end">
        <Button type="button" variant="outline" onClick={handleCancel} disabled={uploadDocument.isPending}>Cancel</Button>
        <Button type="submit" disabled={!file || !projectId} loading={uploadDocument.isPending}>Upload document</Button>
      </div>
    </form>
  )
}
