import type { SessionListItem } from './types'

export function formatSessionLabel(s: SessionListItem): string {
  const date = s.last_message_at
    ? new Date(s.last_message_at)
    : s.created_at
      ? new Date(s.created_at)
      : null
  const dateStr = date
    ? date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'Unknown'
  const msgCount = s.message_count ?? 0
  return `${dateStr} (${msgCount} msg${msgCount !== 1 ? 's' : ''})`
}
