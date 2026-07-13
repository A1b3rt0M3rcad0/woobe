import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { DEFAULT_RETRIEVAL_CONFIG, type RagRuntimeConfig } from '@/features/knowledge/ragConfigTypes'

interface NetworkRagSettingsModalProps {
  open: boolean
  value: RagRuntimeConfig
  onClose: () => void
  onApply: (value: RagRuntimeConfig) => void
}

function numberValue(value: string, fallback: number) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

export function NetworkRagSettingsModal({ open, value, onClose, onApply }: NetworkRagSettingsModalProps) {
  const [draft, setDraft] = useState<RagRuntimeConfig>(value)

  useEffect(() => {
    if (open) setDraft(value)
  }, [open, value])

  const setNumber = (key: keyof RagRuntimeConfig, raw: string, fallback: number) => {
    setDraft((previous) => ({ ...previous, [key]: numberValue(raw, fallback) }))
  }

  return (
    <Dialog open={open} onClose={onClose} title="Runtime retrieval" className="max-w-3xl overflow-hidden bg-surface/95">
      <div className="space-y-5">
        <div>
          <p className="text-sm font-medium text-white">Search behavior</p>
          <p className="mt-1 text-xs leading-5 text-muted">
            These settings belong to the mutable Agent Draft. They control how vector results become context during runtime.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <label className="text-xs font-medium text-muted">
            Candidate K
            <Input
              type="number"
              min="1"
              className="mt-1.5"
              value={draft.candidate_k}
              onChange={(event) => setNumber('candidate_k', event.target.value, DEFAULT_RETRIEVAL_CONFIG.candidate_k)}
            />
          </label>
          <label className="text-xs font-medium text-muted">
            Top K
            <Input
              type="number"
              min="1"
              className="mt-1.5"
              value={draft.top_k}
              onChange={(event) => setNumber('top_k', event.target.value, DEFAULT_RETRIEVAL_CONFIG.top_k)}
            />
          </label>
          <label className="text-xs font-medium text-muted">
            Minimum score
            <Input
              type="number"
              min="0"
              max="1"
              step="0.01"
              className="mt-1.5"
              value={draft.min_score ?? ''}
              placeholder="Optional"
              onChange={(event) => setDraft((previous) => ({
                ...previous,
                min_score: event.target.value.trim() ? numberValue(event.target.value, 0) : null,
              }))}
            />
          </label>
          <label className="text-xs font-medium text-muted">
            Max context chunks
            <Input
              type="number"
              min="1"
              className="mt-1.5"
              value={draft.max_context_chunks}
              onChange={(event) => setNumber('max_context_chunks', event.target.value, DEFAULT_RETRIEVAL_CONFIG.max_context_chunks)}
            />
          </label>
          <label className="text-xs font-medium text-muted">
            Chunks per document
            <Input
              type="number"
              min="1"
              className="mt-1.5"
              value={draft.max_chunks_per_document}
              onChange={(event) => setNumber('max_chunks_per_document', event.target.value, DEFAULT_RETRIEVAL_CONFIG.max_chunks_per_document)}
            />
          </label>
          <label className="text-xs font-medium text-muted">
            Max context characters
            <Input
              type="number"
              min="1000"
              step="1000"
              className="mt-1.5"
              value={draft.max_context_chars}
              onChange={(event) => setNumber('max_context_chars', event.target.value, DEFAULT_RETRIEVAL_CONFIG.max_context_chars)}
            />
          </label>
          <label className="text-xs font-medium text-muted">
            Query mode
            <Select
              className="mt-1.5"
              value={draft.query_mode}
              onChange={(event) => setDraft((previous) => ({
                ...previous,
                query_mode: event.target.value === 'current_message' ? 'current_message' : 'conversation_context',
              }))}
              options={[
                { value: 'conversation_context', label: 'Conversation context' },
                { value: 'current_message', label: 'Current message' },
              ]}
            />
          </label>
          <label className="text-xs font-medium text-muted">
            History turns
            <Input
              type="number"
              min="0"
              className="mt-1.5"
              value={draft.history_turns}
              onChange={(event) => setNumber('history_turns', event.target.value, DEFAULT_RETRIEVAL_CONFIG.history_turns)}
            />
          </label>
          <label className="text-xs font-medium text-muted">
            Grounding policy
            <Select
              className="mt-1.5"
              value={draft.grounding_policy}
              onChange={(event) => setDraft((previous) => ({
                ...previous,
                grounding_policy: event.target.value === 'required' ? 'required' : 'optional',
              }))}
              options={[
                { value: 'optional', label: 'Optional grounding' },
                { value: 'required', label: 'Required grounding' },
              ]}
            />
          </label>
        </div>

        <div className="flex justify-end gap-2 border-t border-border/80 pt-4">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            type="button"
            onClick={() => {
              onApply(draft)
              onClose()
            }}
          >
            Apply settings
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
