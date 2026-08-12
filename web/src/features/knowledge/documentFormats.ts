export const ACCEPTED_DOCUMENT_EXTENSIONS = ['.txt', '.md', '.pdf', '.docx'] as const

export const ACCEPTED_DOCUMENT_MIME_TYPES = [
  'text/plain',
  'text/markdown',
  'text/x-markdown',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/octet-stream',
  'application/zip',
] as const

const FILE_PICKER_MIME_TYPES = [
  'text/plain',
  'text/markdown',
  'text/x-markdown',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
] as const

export const MAX_DOCUMENT_FILE_MB = 25

export const DOCUMENT_ACCEPT_ATTRIBUTE = [
  ...ACCEPTED_DOCUMENT_EXTENSIONS,
  ...FILE_PICKER_MIME_TYPES,
].join(',')

export function extensionOf(fileName: string): string {
  const dotIndex = fileName.lastIndexOf('.')
  return dotIndex >= 0 ? fileName.slice(dotIndex).toLowerCase() : ''
}

export function titleFromDocumentFileName(fileName: string): string {
  return fileName.replace(/\.[^/.]+$/, '')
}

export function validateKnowledgeDocumentFile(candidate: File): string | null {
  const extension = extensionOf(candidate.name)
  if (!ACCEPTED_DOCUMENT_EXTENSIONS.includes(extension as (typeof ACCEPTED_DOCUMENT_EXTENSIONS)[number])) {
    return 'Only TXT, MD, PDF and DOCX files are supported.'
  }
  if (candidate.type && !ACCEPTED_DOCUMENT_MIME_TYPES.includes(candidate.type as (typeof ACCEPTED_DOCUMENT_MIME_TYPES)[number])) {
    return `Invalid file type: ${candidate.type}`
  }
  if (candidate.size <= 0) return 'File is empty.'
  if (candidate.size > MAX_DOCUMENT_FILE_MB * 1024 * 1024) {
    return `File exceeds ${MAX_DOCUMENT_FILE_MB} MB.`
  }
  return null
}
