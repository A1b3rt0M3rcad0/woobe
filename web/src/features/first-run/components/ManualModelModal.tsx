import { useEffect, useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'

interface ManualModelModalProps {
  open: boolean
  onClose: () => void
  initialIdentifier?: string
  initialName?: string
  onConfirm: (identifier: string, name?: string) => void
}

export function ManualModelModal({
  open,
  onClose,
  initialIdentifier = '',
  initialName = '',
  onConfirm,
}: ManualModelModalProps) {
  const [identifier, setIdentifier] = useState('')
  const [name, setName] = useState('')

  useEffect(() => {
    if (!open) return
    setIdentifier(initialIdentifier)
    setName(initialName)
  }, [open, initialIdentifier, initialName])

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    const resolvedIdentifier = identifier.trim()
    if (!resolvedIdentifier) return
    onConfirm(resolvedIdentifier, name.trim() || undefined)
    onClose()
  }

  return (
    <Dialog open={open} onClose={onClose} title="Enter model ID" className="max-w-xl">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-muted">Model ID</label>
          <Input
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
            placeholder="deepseek/deepseek-chat"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            autoFocus
            className="h-10"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-muted">
            Display name <span className="font-normal text-muted/70">(optional)</span>
          </label>
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Defaults to the model ID"
            className="h-10"
          />
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-border/80 pt-4">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={!identifier.trim()}>Use model</Button>
        </div>
      </form>
    </Dialog>
  )
}
