import { useEffect, useState, type FormEvent } from 'react'
import { Button, Dialog, Field, FieldDescription, FieldLabel, Input } from '@woobe/ui'

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
    <Dialog open={open} onClose={onClose} title="Enter model ID" className="max-w-dialog">
      <form onSubmit={handleSubmit} className="grid gap-ui-md">
        <Field>
          <FieldLabel>Model ID</FieldLabel>
          <Input value={identifier} onChange={(event) => setIdentifier(event.target.value)} placeholder="deepseek/deepseek-chat" autoCapitalize="none" autoCorrect="off" spellCheck={false} autoFocus className="font-mono" />
          <FieldDescription>Use the exact model identifier exposed by the provider.</FieldDescription>
        </Field>
        <Field>
          <FieldLabel>Display name <span className="font-normal text-muted-foreground">(optional)</span></FieldLabel>
          <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Defaults to the model ID" />
        </Field>
        <div className="flex items-center justify-end gap-ui-sm border-t border-border pt-ui-md">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={!identifier.trim()}>Use model</Button>
        </div>
      </form>
    </Dialog>
  )
}
