import { get, post, put } from '@/lib/api/client'
import { ApiError } from '@/lib/api/errors'

export type ResourceKind = 'Agent' | 'Network'
export type RecordData = Record<string, unknown>
export interface Draft {
  draft_id: string; resource_uid: string; name: string; generation: number
  working_revision_id: string | null; origin: RecordData; definition_digest: string
}
export interface EditorFile { path: string; content: string | null; editable: boolean; readonly_reason?: string }
export interface Editor { draft: Draft; files: EditorFile[]; entrypoint_path: string }
export interface Current { snapshot_id: string | null; environment_generation: number; selection_authority: string }
export interface Ledger { records: RecordData[]; watermark: unknown; has_more: boolean; next_cursor: string | null }
export interface Pending { operation_id: string; action: string; generation?: number }
export interface LeaseProof { lease_id: string; workflow_id: string; fencing_token: number }

export function ownerPath(project: string, kind: ResourceKind, id: string) {
  return `/projects/${encodeURIComponent(project)}/${kind.toLowerCase()}s/${encodeURIComponent(id)}/asac`
}

export function confirmedRejection(error: unknown): boolean {
  return error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 408
}

export async function ledgerPage(base: string, section: string, cursor?: string, watermark?: unknown): Promise<Ledger> {
  const path = section === 'revisions' ? '/revisions' : '/history'
  const data = await get<Ledger>(base + path, { params: { stream: section === 'revisions' ? undefined : section, limit: 100, cursor } })
  if (watermark !== undefined && JSON.stringify(data.watermark) !== JSON.stringify(watermark)) throw new Error('History watermark changed. Refresh this observation.')
  if (data.has_more && !data.next_cursor) throw new Error('History is incomplete without a continuation cursor.')
  return data
}

export function saveEditor(base: string, editor: Editor, values: Record<string, string>, operation: string) {
  const files = editor.files.filter(file => file.editable && values[file.path] !== file.content)
    .map(file => ({ path: file.path, content: values[file.path] }))
  if (!files.length) throw new Error('No author files changed.')
  return put<Draft>(`${base}/drafts/${editor.draft.draft_id}/editor`, {
    operation_id: operation, expected_generation: editor.draft.generation, files,
  }, { sensitive: true })
}

export function readEditor(base: string, draft: string) {
  return get<Editor>(`${base}/drafts/${draft}/editor`, { sensitive: true })
}

export function mutation(base: string, path: string, body: RecordData, operation: string) {
  return post<RecordData>(base + path, { ...body, operation_id: operation }, { sensitive: true })
}

export function text(record: RecordData | undefined, field: string): string {
  const value = record?.[field]
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '—'
}

export function leaseProof(record: RecordData): LeaseProof {
  if (typeof record.lease_id !== 'string' || typeof record.workflow_id !== 'string'
      || !Number.isSafeInteger(record.fencing_token) || Number(record.fencing_token) < 1) throw new Error('Lease proof is incomplete; reconcile the original operation.')
  return { lease_id: record.lease_id, workflow_id: record.workflow_id, fencing_token: Number(record.fencing_token) }
}
