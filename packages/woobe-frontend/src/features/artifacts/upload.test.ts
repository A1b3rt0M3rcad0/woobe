import { afterEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  beginArtifactUpload: vi.fn(),
  finalizeArtifactUpload: vi.fn(),
  getArtifactUploadStatus: vi.fn(),
  uploadArtifactPart: vi.fn(),
}))

vi.mock('./api', () => api)

import { sha256File, uploadArtifactFile } from './upload'
import type { ArtifactCapabilities } from './types'

const capabilities: ArtifactCapabilities = {
  schema_version: '1', max_upload_bytes: 100, max_upload_part_bytes: 3,
  max_upload_parts: 10, max_inline_bytes: 100, max_request_bytes: 100,
  storage_readiness: 'ready', media_types: [], downloads: [],
}

afterEach(() => vi.clearAllMocks())

describe('Artifact Workspace browser uploads', () => {
  it('hashes files incrementally across chunk boundaries', async () => {
    const file = new File(['abc'], 'example.txt')
    await expect(sha256File(file, 2)).resolves.toBe(
      'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
    )
  })

  it('reconciles a lost part acknowledgement before continuing bounded upload', async () => {
    const file = new File(['abcdef'], 'report.txt', { type: 'text/plain' })
    api.beginArtifactUpload.mockResolvedValue({ id: 'upload-1', status: 'created', offset: 0 })
    api.uploadArtifactPart
      .mockRejectedValueOnce(new TypeError('connection closed after send'))
      .mockResolvedValueOnce({ id: 'upload-1', status: 'uploading', offset: 6 })
    api.getArtifactUploadStatus.mockResolvedValue({ id: 'upload-1', status: 'uploading', offset: 3 })
    api.finalizeArtifactUpload.mockResolvedValue({
      id: 'upload-1', status: 'committed', offset: 6,
      receipt: { artifact_id: 'artifact-1', revision_id: 'revision-1' },
    })
    const progress: number[] = []

    const result = await uploadArtifactFile(
      { projectId: 'project-1', environment: 'draft' },
      'workspace-1', file, 'reports/report.txt', capabilities,
      value => progress.push(value), 'operation-1',
    )

    expect(result.status).toBe('committed')
    expect(result.receipt?.revision_id).toBe('revision-1')
    expect(api.beginArtifactUpload).toHaveBeenCalledWith(
      { projectId: 'project-1', environment: 'draft' },
      'workspace-1',
      expect.objectContaining({
        operation_id: 'operation-1', path: 'reports/report.txt', size_bytes: 6,
        sha256: 'bef57ec7f53a6d40beb640a780a639c83bc29ac8a9816f1fc6c5c6dcd93c4721',
      }),
      undefined,
    )
    expect(api.uploadArtifactPart).toHaveBeenNthCalledWith(
      1, { projectId: 'project-1', environment: 'draft' }, 'workspace-1', 'upload-1', 0, expect.any(Blob), undefined,
    )
    expect(api.getArtifactUploadStatus).toHaveBeenCalledOnce()
    expect(api.uploadArtifactPart).toHaveBeenCalledTimes(2)
    expect(api.finalizeArtifactUpload).toHaveBeenCalledOnce()
    expect(progress).toEqual([0, 3, 6])
  })

  it('rejects a file above the advertised limit before creating an upload', async () => {
    const file = new File(['x'.repeat(101)], 'too-large.bin')
    await expect(uploadArtifactFile(
      { projectId: 'project-1', environment: 'draft' }, 'workspace-1',
      file, file.name, capabilities, undefined, 'operation-2',
    )).rejects.toThrow('upload limit')
    expect(api.beginArtifactUpload).not.toHaveBeenCalled()
  })

  it('pauses an upload on cancellation and resumes the same operation safely', async () => {
    const file = new File(['abcdef'], 'resume.txt')
    const controller = new AbortController()
    api.beginArtifactUpload.mockResolvedValue({ id: 'upload-resume', status: 'created', offset: 0 })
    api.uploadArtifactPart.mockImplementationOnce(() => {
      controller.abort()
      throw new DOMException('The operation was aborted', 'AbortError')
    }).mockResolvedValueOnce({ id: 'upload-resume', status: 'uploading', offset: 3 })
      .mockResolvedValueOnce({ id: 'upload-resume', status: 'uploading', offset: 6 })
    api.finalizeArtifactUpload.mockResolvedValue({
      id: 'upload-resume', status: 'committed', offset: 6,
      receipt: { artifact_id: 'artifact-1', revision_id: 'revision-2' },
    })

    await expect(uploadArtifactFile(
      { projectId: 'project-1', environment: 'draft' }, 'workspace-1', file, 'resume.txt',
      capabilities, undefined, 'stable-operation', controller.signal,
    )).rejects.toMatchObject({ name: 'AbortError' })

    await expect(uploadArtifactFile(
      { projectId: 'project-1', environment: 'draft' }, 'workspace-1', file, 'resume.txt',
      capabilities, undefined, 'stable-operation',
    )).resolves.toMatchObject({ status: 'committed', receipt: { revision_id: 'revision-2' } })
    expect(api.beginArtifactUpload).toHaveBeenNthCalledWith(1, expect.anything(), expect.anything(), expect.objectContaining({ operation_id: 'stable-operation' }), controller.signal)
    expect(api.beginArtifactUpload).toHaveBeenNthCalledWith(2, expect.anything(), expect.anything(), expect.objectContaining({ operation_id: 'stable-operation' }), undefined)
  })
})
