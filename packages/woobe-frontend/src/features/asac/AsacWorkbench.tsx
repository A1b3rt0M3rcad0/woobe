import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { get, post } from '@/lib/api/client'
import { confirmedRejection, ledgerPage, leaseProof, mutation, ownerPath, readEditor, saveEditor, text } from './api'
import type { Current, Draft, Editor, Ledger, LeaseProof, Pending, RecordData, ResourceKind } from './api'

const box = 'rounded-container border border-border bg-background/25 p-ui-md'
const label = 'font-mono text-system-meta text-muted-foreground'
const tabs = ['drafts', 'revisions', 'releases', 'deployments'] as const
const field = (title: string, child: ReactNode) => <label className="min-w-0 space-y-ui-xs"><span className={label}>{title}</span>{child}</label>

export function AsacWorkbench({ projectId, resourceId, kind }: { projectId: string; resourceId: string; kind: ResourceKind }) {
  const base = ownerPath(projectId, kind, resourceId)
  const storage = `woobe-asac-pending:${projectId}:${kind}:${resourceId}`
  const [tab, setTab] = useState<typeof tabs[number]>('drafts')
  const [draftId, setDraftId] = useState('')
  const [editor, setEditor] = useState<Editor | null>(null)
  const [comparison, setComparison] = useState<Editor | null>(null)
  const [values, setValues] = useState<Record<string, string>>({})
  const [file, setFile] = useState('')
  const [name, setName] = useState('hotfix')
  const [source, setSource] = useState('production')
  const [version, setVersion] = useState('')
  const [reason, setReason] = useState('')
  const [parents, setParents] = useState<string[]>([])
  const [ledger, setLedger] = useState<Ledger | null>(null)
  const [candidate, setCandidate] = useState<RecordData | null>(null)
  const [evaluation, setEvaluation] = useState<RecordData | null>(null)
  const [publication, setPublication] = useState<RecordData | null>(null)
  const [plan, setPlan] = useState<RecordData | null>(null)
  const [proof, setProof] = useState<LeaseProof | null>(null)
  const [environment, setEnvironment] = useState('production')
  const [testInput, setTestInput] = useState('Hello')
  const [expected, setExpected] = useState('')
  const [suite, setSuite] = useState('web-acceptance')
  const [suiteVersion, setSuiteVersion] = useState('1')
  const [pending, setPending] = useState<Pending | null>(() => {
    try { return JSON.parse(sessionStorage.getItem(storage) ?? 'null') as Pending | null } catch { return null }
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [observed, setObserved] = useState(0)
  const [now, setNow] = useState(Date.now())
  const drafts = useQuery({ queryKey: ['asac-drafts', base], queryFn: () => get<{ drafts: Draft[] }>(base + '/drafts'), refetchInterval: 15000 })
  const production = useQuery({ queryKey: ['asac-production', base], queryFn: () => get<Current>(base + '/current', { params: { environment: 'production' } }), refetchInterval: 15000 })
  const remoteDraft = useQuery({ queryKey: ['asac-draft', base, draftId], queryFn: () => get<Draft>(`${base}/drafts/${draftId}`), enabled: Boolean(draftId), refetchInterval: 15000 })
  const dirty = Boolean(editor?.files.some(item => item.editable && values[item.path] !== item.content))
  const stale = Boolean(editor && remoteDraft.data && editor.draft.generation !== remoteDraft.data.generation)
  const blocked = busy || pending !== null
  const files = useMemo(() => editor?.files.filter(item => item.editable) ?? [], [editor])
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 10000); return () => window.clearInterval(timer) }, [])
  useEffect(() => { setLedger(null) }, [tab])
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = '' } }
    window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  function remember(value: Pending | null) {
    setPending(value)
    if (value) sessionStorage.setItem(storage, JSON.stringify(value)); else sessionStorage.removeItem(storage)
  }
  function accept(action: string, result: RecordData) {
    if (action === 'open') { setDraftId(String(result.draft_id)); setEditor(null) }
    if (action === 'stage') { setCandidate(result); setEvaluation(null); setPublication(null); setPlan(null) }
    if (action === 'evaluate') setEvaluation(result)
    if (action === 'publish') { setPublication(result); setPlan(null) }
    if (action === 'plan') { setPlan(result); setProof(null) }
    if (action === 'lease') setProof(leaseProof(result))
    if (action === 'release') setProof(null)
    if (action === 'apply') { setNotice('Deployment committed. Refresh history to inspect the owner receipt.'); void production.refetch() }
    if (action === 'checkpoint' && editor) {
      const record = result.record as RecordData
      setEditor({ ...editor, draft: { ...editor.draft, working_revision_id: String(record.revision_id) } })
      setParents([String(record.revision_id)])
    }
    void drafts.refetch(); void remoteDraft.refetch()
  }
  async function write(action: string, execute: (operation: string) => Promise<RecordData>) {
    if (blocked) return
    const operation = crypto.randomUUID()
    try { remember({ operation_id: operation, action, generation: editor?.draft.generation }) } catch { setError('Cannot preserve an operation checkpoint in this browser.'); return }
    setBusy(true); setError(''); setNotice('')
    try { const result = await execute(operation); accept(action, result); remember(null) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Operation outcome is uncertain.'); if (confirmedRejection(caught)) remember(null) }
    finally { setBusy(false) }
  }
  async function loadEditor(id = draftId) {
    if (dirty || blocked) { setError('Keep your edits or save them before replacing this editor.'); return }
    setBusy(true); setError('')
    try {
      const data = await readEditor(base, id)
      setDraftId(id); setComparison(null); setEditor(data); setValues(Object.fromEntries(data.files.filter(item => item.editable).map(item => [item.path, item.content!]))); setFile(data.entrypoint_path)
      setParents(data.draft.working_revision_id ? [data.draft.working_revision_id] : []); setObserved(Date.now())
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Editor unavailable.') }
    finally { setBusy(false) }
  }
  async function compareRemote() {
    setBusy(true); setError('')
    try { setComparison(await readEditor(base, draftId)) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Comparison unavailable.') }
    finally { setBusy(false) }
  }
  function downloadEditedFile() {
    const url = URL.createObjectURL(new Blob([values[file] ?? ''], { type: 'text/yaml;charset=utf-8' }))
    const link = document.createElement('a'); link.href = url; link.download = file.split('/').pop() ?? 'author.yaml'; link.click(); URL.revokeObjectURL(url)
  }
  function discardEditor() {
    if (!window.confirm('Discard these local edits? Download any files you need before continuing.')) return
    setEditor(null); setValues({}); setComparison(null); setNotice('Local edits discarded. Load the current saved files explicitly.')
  }
  async function history(more = false) {
    setBusy(true); setError('')
    try {
      const page = await ledgerPage(base, tab, more ? ledger?.next_cursor ?? undefined : undefined, more ? ledger?.watermark : undefined)
      setLedger({ ...page, records: more ? [...ledger!.records, ...page.records] : page.records }); setObserved(Date.now())
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'History unavailable.') }
    finally { setBusy(false) }
  }
  async function inspect(target: 'candidate' | 'evaluation') {
    const record = target === 'candidate' ? candidate : evaluation
    if (!record) return
    setBusy(true); setError('')
    try {
      const id = text(record, target === 'candidate' ? 'candidate_id' : 'evaluation_id')
      const result = await get<RecordData>(`${base}/${target === 'candidate' ? 'candidates' : 'evaluations'}/${id}`)
      if (target === 'candidate') setCandidate(result); else setEvaluation(result)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Observation failed.') }
    finally { setBusy(false) }
  }
  async function reconcile() {
    if (!pending) return
    setBusy(true); setError('')
    try {
      const result = await get<RecordData>(`${base}/operations/${pending.operation_id}`, { sensitive: true })
      if (result.state !== 'committed') throw new Error('Original outcome is not yet observed. No retry is authorized.')
      accept(pending.action, result.result as RecordData); remember(null); setNotice('Original operation recovered. Refresh the selected Draft before another edit.')
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Reconciliation failed.') }
    finally { setBusy(false) }
  }
  async function open() {
    if (blocked || dirty) return
    setBusy(true); setError('')
    let exported: RecordData
    try {
      // Capture first: failures here have not submitted an owner mutation.
      exported = await post<RecordData>(`/projects/${projectId}/packages/export`, { kind, target_id: resourceId, source, ...(source === 'release' ? { release_version: version } : {}), knowledge: 'portable', development: true }, { sensitive: true })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Snapshot capture failed.'); setBusy(false); return
    }
    setBusy(false)
    await write('open', async operation => {
      const uid = (exported.source as RecordData).resource_uid ?? drafts.data?.drafts[0]?.resource_uid ?? crypto.randomUUID()
      const result = await mutation(base, '/drafts', { name, resource_uid: uid, source_export_id: exported.export_id }, operation)
      setDraftId(String(result.draft_id)); setEditor(null); setNotice('Isolated Draft opened; load its files to edit. Production is unchanged.')
      return result
    })
  }
  async function prepareDeployment() {
    if (blocked || !publication) return
    setBusy(true); setError('')
    let current: Current
    try { current = await get<Current>(base + '/current', { params: { environment } }) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Current selection unavailable.'); setBusy(false); return }
    setBusy(false)
    await write('plan', operation => mutation(base, '/deployment-plans', { release_id: publication.release_id, publication_id: publication.publication_id, environment, expected_generation: current.environment_generation, reason }, operation))
  }
  const draftControls = <div className="space-y-ui-md">
    <div className={`${box} grid items-end gap-ui-md md:grid-cols-[1fr_1fr_auto]`}>
      {field('Isolated Draft', <Select aria-label="Isolated Draft" value={draftId} onChange={event => { if (dirty) { setError('Save your local edits before selecting another Draft.'); return }; setDraftId(event.target.value); setEditor(null) }} options={(drafts.data?.drafts ?? []).map(item => ({ value: item.draft_id, label: `${item.name} · generation ${item.generation}` }))} placeholder="Select a Draft" disabled={blocked} />)}
      <p className={label}>Production: {production.data?.snapshot_id ?? 'not observed'} · generation {production.data?.environment_generation ?? '—'}</p>
      <Button onClick={() => void loadEditor()} disabled={!draftId || blocked || dirty}>Load saved files</Button>
    </div>
    <div className={`${box} grid items-end gap-ui-md md:grid-cols-4`}>
      {field('New Draft name', <Input value={name} onChange={event => setName(event.target.value)} aria-label="New Draft name" />)}
      {field('Open from', <Select value={source} onChange={event => setSource(event.target.value)} aria-label="Open from" options={['draft', 'staging', 'release', 'production'].map(value => ({ value, label: value }))} />)}
      {field('Release version', <Input value={version} disabled={source !== 'release'} onChange={event => setVersion(event.target.value)} aria-label="Release version" placeholder="Only for a fixed Release" />)}
      <Button onClick={() => void open()} disabled={blocked || dirty || !name || (source === 'release' && !version)}>Open isolated Draft</Button>
    </div>
    {editor && <div className={`${box} space-y-ui-md`}>
      <div className="grid gap-ui-sm md:grid-cols-3"><span className={label}>Origin: {text(editor.draft.origin, 'environment')} / {text(editor.draft.origin, 'snapshot_id')}</span><span className={label}>Selected Draft: {editor.draft.name} · generation {editor.draft.generation}</span><span className={label}>Writes update this Draft. Stage and Production are separate.</span></div>
      {stale && <p role="alert" className="text-amber-300">The remote generation changed. Your edits remain here; saving is blocked. Compare and resolve before refreshing.</p>}
      {stale && <div className="flex flex-wrap gap-ui-sm"><Button disabled={blocked} onClick={() => void compareRemote()}>Compare remote files</Button><Button variant="outline" disabled={blocked} onClick={discardEditor}>Discard local edits</Button></div>}
      {field('Author file', <Select aria-label="Author file" value={file} onChange={event => setFile(event.target.value)} options={files.map(item => ({ value: item.path, label: item.path }))} />)}
      <textarea aria-label="Author YAML" value={values[file] ?? ''} onChange={event => setValues({ ...values, [file]: event.target.value })} disabled={blocked} spellCheck={false} className="min-h-[340px] w-full rounded-control border border-border bg-background p-ui-md font-mono text-xs leading-5" />
      <Button variant="outline" onClick={downloadEditedFile}>Download selected author file</Button>
      {comparison && <div className="space-y-ui-xs"><p className={label}>Read-only remote comparison · generation {comparison.draft.generation}. Local edits above are preserved.</p><textarea readOnly aria-label="Remote author YAML" value={comparison.files.find(item => item.path === file)?.content ?? 'File unavailable in this remote closure.'} className="min-h-[240px] w-full rounded-control border border-border bg-background p-ui-md font-mono text-xs" /></div>}
      <div className="grid items-end gap-ui-md md:grid-cols-[1fr_auto_auto]">{field('Checkpoint / publication reason', <Input value={reason} onChange={event => setReason(event.target.value)} aria-label="Checkpoint reason" />)}
        <Button disabled={blocked || !dirty || stale} onClick={() => void write('save', async operation => { const result = await saveEditor(base, editor, values, operation); setEditor({ ...editor, draft: result, files: editor.files.map(item => item.editable ? { ...item, content: values[item.path] } : item) }); return result as unknown as RecordData })}>Save this Draft</Button>
        <Button disabled={blocked || dirty || stale || !reason.trim()} onClick={() => void write('checkpoint', operation => mutation(base, `/drafts/${draftId}/checkpoint`, { expected_generation: editor.draft.generation, revision_id: `rv_${crypto.randomUUID()}`, message: reason, parents }, operation))}>Create checkpoint</Button>
      </div>
      <p className={label}>Working checkpoint: {editor.draft.working_revision_id ?? 'none'} · schema/reference validation runs on save; semantic qualification runs at Stage.</p>
      <Button disabled={blocked || dirty || stale || !editor.draft.working_revision_id} onClick={() => void write('stage', operation => mutation(base, `/drafts/${draftId}/stage`, { expected_generation: editor.draft.generation, revision_id: editor.draft.working_revision_id }, operation))}>Prepare exact checkpoint</Button>
    </div>}
  </div>
  return <div className="space-y-ui-md">
    <div role="tablist" aria-label={`${kind} ASaC lifecycle`} className="flex flex-wrap gap-ui-xs">{tabs.map(item => <button type="button" role="tab" aria-selected={item === tab} key={item} className={`${box} py-ui-xs capitalize ${item === tab ? 'text-primary-light' : 'text-muted-foreground'}`} onClick={() => setTab(item)}>{item}</button>)}</div>
    {error && <p role="alert" className="text-sm text-amber-300">{error}</p>}
    {notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
    {pending && <div className={box}><p className={label}>Uncertain {pending.action} operation {pending.operation_id}. New writes are blocked.</p><Button disabled={busy} onClick={() => void reconcile()}>Reconcile original operation</Button></div>}
    {drafts.isError && <p role="alert">Drafts are unavailable under the current grants.</p>}
    {observed > 0 && <p className={label}>Observation age: {Math.floor((now - observed) / 1000)}s{now - observed > 60000 ? ' · refresh before relying on current selection' : ''}</p>}
    {tab === 'drafts' ? draftControls : <div className={`${box} space-y-ui-md`}>
      <div className="flex items-center justify-between"><p className={label}>Owner-scoped history. {ledger?.has_more ? 'More pages remain.' : ledger ? 'Complete through this observation watermark.' : 'Not yet observed.'}</p><Button disabled={busy} onClick={() => void history()}>Refresh {tab}</Button></div>
      <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr>{['Identity', 'Version / revision', 'State / action', 'Actor', 'Created'].map(title => <th key={title} className="p-ui-sm font-mono text-muted-foreground">{title}</th>)}</tr></thead><tbody>{(ledger?.records ?? []).map((item, index) => { const record = item.record as RecordData | undefined; return <tr key={`${text(item, 'id')}-${index}`} className="border-t border-border"><td className="p-ui-sm font-mono">{record ? text(record, 'revision_id') : text(item, 'deployment_id') !== '—' ? text(item, 'deployment_id') : text(item, 'release_id') !== '—' ? text(item, 'release_id') : text(item, 'id')}</td><td className="p-ui-sm">{record ? text(record, 'message') : text(item, 'version')}</td><td className="p-ui-sm">{text(item, tab === 'deployments' ? 'action' : 'status')}</td><td className="p-ui-sm">{text(item, 'actor')}</td><td className="p-ui-sm">{text(item, 'created_at')}</td></tr> })}</tbody></table></div>
      {ledger?.has_more && <Button disabled={busy} onClick={() => void history(true)}>Load next page</Button>}
    </div>}
    {candidate && <div className={`${box} space-y-ui-md`}>
      <div className="flex flex-wrap items-center justify-between gap-ui-sm"><p className={label}>Candidate {text(candidate, 'candidate_id')} · {text(candidate, 'state')} · checkpoint {text(candidate, 'revision_id')}</p><Button disabled={busy} onClick={() => void inspect('candidate')}>Refresh Candidate</Button></div>
      <div className="grid gap-ui-md md:grid-cols-3">{field('Suite identity', <Input value={suite} onChange={event => setSuite(event.target.value)} />)}{field('Suite / dataset version', <Input value={suiteVersion} onChange={event => setSuiteVersion(event.target.value)} />)}{field('Exact expected text (optional)', <Input value={expected} onChange={event => setExpected(event.target.value)} />)}</div>
      {field('Acceptance case input', <textarea value={testInput} onChange={event => setTestInput(event.target.value)} className="w-full rounded-control border border-border bg-background p-ui-sm text-xs" aria-label="Acceptance case input" />)}
      <Button disabled={blocked || candidate.state !== 'ready' || !testInput.trim() || !suite || !suiteVersion} onClick={() => void write('evaluate', operation => mutation(base, `/candidates/${text(candidate, 'candidate_id')}/evaluations`, { suite: { schema_version: '1.0', suite_id: suite, suite_version: suiteVersion, dataset_version: suiteVersion, cases: [{ id: 'web-case', message: testInput, ...(expected ? { expected_output: expected } : {}) }] } }, operation))}>Evaluate this Candidate</Button>
      {evaluation && <div className="flex items-center justify-between"><p className={label}>Evaluation {text(evaluation, 'evaluation_id')} · {text(evaluation, 'state')}</p><Button disabled={busy} onClick={() => void inspect('evaluation')}>Refresh evaluation</Button></div>}
      <Button disabled={blocked || evaluation?.state !== 'passed' || reason.trim().length < 3} onClick={() => void write('publish', operation => mutation(base, '/publications', { candidate_id: candidate.candidate_id, evaluation_id: evaluation!.evaluation_id, reason }, operation))}>Publish tested Candidate · Production unchanged</Button>
    </div>}
    {publication && <div className={`${box} space-y-ui-md`}>
      <p className={label}>Published Release {text(publication, 'release_version')} / {text(publication, 'release_id')}. Git provenance: unavailable for this Web operation.</p>
      <div className="grid items-end gap-ui-md md:grid-cols-[1fr_2fr_auto]">{field('Deployment environment', <Select value={environment} disabled={Boolean(plan)} onChange={event => setEnvironment(event.target.value)} options={['staging', 'production'].map(value => ({ value, label: value }))} />)}{field('Activation reason', <Input value={reason} onChange={event => setReason(event.target.value)} />)}
        <Button disabled={blocked || reason.trim().length < 3} onClick={() => void prepareDeployment()}>Plan exact activation</Button>
      </div>
      {plan && <div className="space-y-ui-sm"><p className={label}>Plan {text(plan, 'plan_id')} · expected generation {text(plan, 'expected_generation')} · {environment}. Review this selection before applying.</p>
        <div className="flex flex-wrap gap-ui-sm"><Button disabled={blocked || Boolean(proof)} onClick={() => void write('lease', operation => mutation(base, '/leases/acquire', { workflow_id: crypto.randomUUID(), scope: environment, ttl_seconds: 60 }, operation))}>Acquire 60s environment lease</Button>
          <Button disabled={blocked || !proof} onClick={() => void write('apply', operation => mutation(base, '/deployments', { plan_id: plan.plan_id, environment, leases: [proof] }, operation))}>Apply Release to {environment}</Button>
          <Button variant="outline" disabled={blocked || !proof} onClick={() => void write('release', operation => mutation(base, '/leases/release', { ...proof, scope: environment }, operation))}>Release lease</Button>
        </div></div>}
    </div>}
  </div>
}
