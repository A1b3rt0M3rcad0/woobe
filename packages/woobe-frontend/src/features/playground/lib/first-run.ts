import type { ChatMessage } from '@/features/playground/types'

export function isFirstRunSearch(search: string): boolean {
  return new URLSearchParams(search).get('firstRun') === '1'
}

export function didCompleteFirstRun(
  wasSending: boolean,
  isSending: boolean,
  messages: ChatMessage[],
): boolean {
  if (!wasSending || isSending) return false

  const lastAssistantMessage = [...messages]
    .reverse()
    .find((message) => message.role === 'assistant')

  return Boolean(
    lastAssistantMessage?.content.trim()
    && !lastAssistantMessage.output_parse_error,
  )
}

export function removeFirstRunFromLocation(
  pathname: string,
  search: string,
  hash = '',
): string {
  const params = new URLSearchParams(search)
  params.delete('firstRun')
  const nextSearch = params.toString()

  return `${pathname}${nextSearch ? `?${nextSearch}` : ''}${hash}`
}
