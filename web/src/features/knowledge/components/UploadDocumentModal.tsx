import { useState } from 'react'
import { useUploadDocument } from '@/features/knowledge/hooks'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Upload } from 'lucide-react'
import { toast } from 'sonner'

interface UploadDocumentModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  collectionIds: { id: string; name: string }[]
  defaultCollectionId?: string
}

export function UploadDocumentModal({ open, onClose, projectId, collectionIds, defaultCollectionId }: UploadDocumentModalProps) {
  const uploadDocument = useUploadDocument()
  const [collectionId, setCollectionId] = useState(defaultCollectionId || '')
  const [title, setTitle] = useState('')
  const [fileName, setFileName] = useState('')
  const [fileContent, setFileContent] = useState<File | null>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setFileContent(file)
      setFileName(file.name)
      if (!title) setTitle(file.name.replace(/\.[^/.]+$/, ''))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!collectionId) {
      toast.error('Select a collection')
      return
    }
    if (!fileContent) {
      toast.error('Select a file')
      return
    }
    try {
      await uploadDocument.mutateAsync({
        project_id: projectId,
        collection_id: collectionId,
        title: title.trim() || fileName,
        file_name: fileName,
        content_type: fileContent.type || 'application/octet-stream',
        size_bytes: fileContent.size,
        storage_key: `projects/${projectId}/documents/${fileName}`,
      })
      toast.success('Document uploaded')
      setCollectionId('')
      setTitle('')
      setFileName('')
      setFileContent(null)
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to upload document')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Upload Document">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Collection</label>
          {collectionIds.length === 0 ? (
            <p className="text-sm text-muted">No collections available. Create one first.</p>
          ) : (
            <Select
              value={collectionId}
              onChange={(e) => setCollectionId(e.target.value)}
              options={collectionIds.map((c) => ({ value: c.id, label: c.name }))}
              placeholder="Select collection"
            />
          )}
        </div>
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Title (optional)</label>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Document title"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-muted mb-1">File</label>
          <div className="rounded-lg border-2 border-dashed border-border p-6 text-center hover:border-primary/50 transition-colors cursor-pointer">
            <input
              type="file"
              onChange={handleFileChange}
              className="hidden"
              id="file-upload"
            />
            <label htmlFor="file-upload" className="cursor-pointer">
              <Upload className="mx-auto h-8 w-8 text-muted mb-2" />
              {fileContent ? (
                <p className="text-sm text-white">{fileContent.name}</p>
              ) : (
                <p className="text-sm text-muted">Drop file here or click to browse</p>
              )}
            </label>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={collectionIds.length === 0} loading={uploadDocument.isPending}>Upload</Button>
        </div>
      </form>
    </Dialog>
  )
}
