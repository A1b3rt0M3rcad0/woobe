import { useEffect, useState, type FormEvent } from 'react'
import { Field, FieldDescription, FieldLabel } from '@woobe/ui'
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

export function ManualModelModal({ open, onClose, initialIdentifier = '', initialName = '', onConfirm }: ManualModelModalProps) {
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
      <form onSubmit={handleSubmit} className="space-y-3">
        <Field>
          <FieldLabel>Model ID</FieldLabel>
          <Input value={identifier} onChange={(event) => setIdentifier(event.target.value)} placeholder="deepseek/deepseek-chat" autoCapitalize="none" autoCorrect="off" spellCheck={false} autoFocus className="font-mono" />
          <FieldDescription>Use the exact model identifier exposed by the provider.</FieldDescription>
        </Field>
        <Field>
          <FieldLabel>Display name <span className="font-normal text-muted">(optional)</span></FieldLabel>
          <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Defaults to the model ID" />
        </Field>
        <div className="flex items-center justify-end gap-2 border-t border-border pt-3">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={!identifier.trim()}>Use model</Button>
        </div>
      </form>
    </Dialog>
  )
}
