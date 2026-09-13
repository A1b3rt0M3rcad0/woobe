import { useEffect, useRef, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Button,
  Dialog,
  EmptyStatePanel,
  TechnicalListItem,
  Textarea,
} from '@woobe/ui'

import { behaviorFields } from '../behavior'

type Field = (typeof behaviorFields)[number]
type Value = string | string[]

interface Props {
  field: Field
  value: Value
  agentName: string
  onApply: (value: Value) => void
  onClose: () => void
}

export function AgentBehaviorFieldDialog({ field, value, agentName, onApply, onClose }: Props) {
  const [initialValue] = useState<Value>(() => Array.isArray(value) ? [...value] : value)
  const [draft, setDraft] = useState<Value>(() => Array.isArray(value) ? [...value] : value)
  const [item, setItem] = useState<{ index: number; original: string; text: string } | null>(null)
  const [confirmDiscard, setConfirmDiscard] = useState(false)
  const bodyRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const returnFocusRef = useRef(document.activeElement as HTMLElement | null)
  const dirty = JSON.stringify(draft) !== JSON.stringify(initialValue) || Boolean(item && item.text !== item.original)

  useEffect(() => {
    const trigger = returnFocusRef.current
    return () => { trigger?.focus() }
  }, [])

  useEffect(() => {
    if (confirmDiscard) bodyRef.current?.querySelector('button')?.focus()
    else if (textareaRef.current) textareaRef.current.focus()
    else bodyRef.current?.querySelector('button')?.focus()
  }, [confirmDiscard, item?.index])

  const requestClose = () => {
    if (dirty) setConfirmDiscard(true)
    else onClose()
  }

  const applyItem = () => {
    if (!item || !Array.isArray(draft) || !item.text.trim()) return
    setDraft(item.index === -1 ? [...draft, item.text] : draft.map((text, index) => index === item.index ? item.text : text))
    setItem(null)
  }

  return (
    <Dialog
      open
      title={field.label}
      onClose={requestClose}
      className="flex max-h-dialog max-w-dialog flex-col overflow-hidden"
      contentClassName="flex min-h-0 flex-1 flex-col p-0"
    >
      <div ref={bodyRef} aria-label={`Edit ${field.label}`} className="flex min-h-0 flex-1 flex-col">
        {confirmDiscard ? (
          <>
            <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto p-ui-lg">
              <Alert variant="warning" className="w-full">
                <AlertTitle>Discard changes to this field?</AlertTitle>
                <AlertDescription>Your Agent configuration will remain unchanged.</AlertDescription>
              </Alert>
            </div>
            <div className="flex shrink-0 justify-end gap-ui-sm border-t border-border bg-surface/95 px-ui-lg py-ui-md">
              <Button type="button" variant="outline" onClick={() => setConfirmDiscard(false)}>Keep editing</Button>
              <Button type="button" variant="destructive" onClick={onClose}>Discard changes</Button>
            </div>
          </>
        ) : (
          <>
            <div className="flex min-h-0 flex-1 flex-col gap-ui-md overflow-hidden p-ui-lg">
              <div className="shrink-0 border-b border-border pb-ui-md">
                <p className="truncate font-mono text-system-control font-semibold text-accent-foreground">{agentName || 'Unnamed Agent'}</p>
                <p className="mt-ui-xs font-sans text-product-caption leading-4 text-muted-foreground">{field.help}</p>
              </div>

              {Array.isArray(draft) && !item ? (
                <>
                  <div className="flex shrink-0 items-center justify-between gap-ui-md">
                    <span className="font-mono text-system-meta text-muted-foreground">{draft.length} items</span>
                    <Button type="button" size="sm" onClick={() => setItem({ index: -1, original: '', text: '' })}>
                      <Plus className="h-icon-sm w-icon-sm" />Add item
                    </Button>
                  </div>

                  <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-container border border-border bg-background/20 p-ui-xs">
                    {draft.length === 0 ? (
                      <EmptyStatePanel compact title="No items configured" description="Add the first item for this behavior field." />
                    ) : (
                      <div className="grid gap-ui-xs">
                        {draft.map((text, index) => (
                          <TechnicalListItem
                            key={index}
                            label={text || 'Empty item'}
                            trailing={(
                              <div className="flex shrink-0 gap-ui-xs">
                                <Button
                                  type="button"
                                  size="iconSm"
                                  variant="ghost"
                                  aria-label={`Edit ${field.label.toLowerCase()} ${index + 1}`}
                                  onClick={(event) => {
                                    event.stopPropagation()
                                    setItem({ index, original: text, text })
                                  }}
                                >
                                  <Pencil className="h-icon-sm w-icon-sm" />
                                </Button>
                                <Button
                                  type="button"
                                  size="iconSm"
                                  variant="ghost"
                                  aria-label={`Remove ${field.label.toLowerCase()} ${index + 1}`}
                                  onClick={(event) => {
                                    event.stopPropagation()
                                    setDraft(draft.filter((_, itemIndex) => itemIndex !== index))
                                  }}
                                >
                                  <Trash2 className="h-icon-sm w-icon-sm text-error" />
                                </Button>
                              </div>
                            )}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="min-h-0 flex-1 [&>div]:h-full">
                  <Textarea
                    ref={textareaRef}
                    aria-label={item ? `${field.label} item` : field.label}
                    value={item ? item.text : draft as string}
                    onChange={(event) => item ? setItem({ ...item, text: event.target.value }) : setDraft(event.target.value)}
                    placeholder={item ? 'Describe this item...' : field.help}
                    className="scrollbar-thin h-full min-h-0 resize-none overflow-y-auto overscroll-contain bg-background/25 font-sans text-product-body leading-5"
                  />
                </div>
              )}
            </div>

            <div className="flex shrink-0 flex-wrap items-center justify-between gap-ui-md border-t border-border bg-surface/95 px-ui-lg py-ui-md">
              <p className="font-sans text-product-caption text-muted-foreground">
                {item ? 'Apply this item, then apply the field changes.' : 'Apply locally, then save the Agent Draft.'}
              </p>
              <div className="ml-auto flex gap-ui-sm">
                {item ? (
                  <>
                    <Button type="button" variant="outline" onClick={() => setItem(null)}>Cancel item</Button>
                    <Button type="button" disabled={!item.text.trim()} onClick={applyItem}>{item.index === -1 ? 'Add item' : 'Apply item'}</Button>
                  </>
                ) : (
                  <>
                    <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
                    <Button type="button" onClick={() => { onApply(draft); onClose() }}>Apply changes</Button>
                  </>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </Dialog>
  )
}
