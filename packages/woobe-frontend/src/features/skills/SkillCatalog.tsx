import { useEffect, useRef, useState, type InputHTMLAttributes } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Download, Plus, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { getSkillVersion, importSkill, listSkills, listSkillVersions } from './api'
import { readSkillFiles } from './config'
import type { Skill, SkillBinding, SkillSnapshot } from './types'

const directoryProps = { webkitdirectory: '' } as InputHTMLAttributes<HTMLInputElement>
const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Unable to complete this action.'

export type SkillCatalogMode = 'browse' | 'create' | 'import'
export interface SkillCatalogProps {
  projectId: string
  bindings?: SkillBinding[]
  onInstall?: (version: SkillSnapshot) => void
  managerName?: string
  initialMode?: SkillCatalogMode
  initialVersionId?: string
  installDisabled?: boolean
  onBusyChange?: (busy: boolean) => void
  showCreateActions?: boolean
}

export function SkillCatalog({ projectId, bindings = [], onInstall, managerName, initialMode = 'browse', initialVersionId, installDisabled = false, onBusyChange, showCreateActions = true }: SkillCatalogProps) {
  const queryClient = useQueryClient()
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<Skill | null>(null)
  const [versionOffset, setVersionOffset] = useState(0)
  const [importing, setImporting] = useState(initialMode !== 'browse')
  const [creating, setCreating] = useState(initialMode === 'create')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [instructions, setInstructions] = useState('')
  const [version, setVersion] = useState('1.0.0')
  const [skillMd, setSkillMd] = useState('')
  const [resources, setResources] = useState<Record<string, string>>({})
  const [requiredTools, setRequiredTools] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<SkillSnapshot | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)
  const catalog = useQuery({ queryKey: ['skills', projectId, query, offset], queryFn: () => listSkills(projectId, query, offset) })
  const versions = useQuery({ queryKey: ['skill-versions', projectId, selected?.id, versionOffset], queryFn: () => listSkillVersions(projectId, selected!.id, versionOffset), enabled: !!selected && !importing })

  useEffect(() => { onBusyChange?.(busy) }, [busy, onBusyChange])
  useEffect(() => {
    if (!initialVersionId) return
    let cancelled = false
    setBusy(true)
    getSkillVersion(projectId, initialVersionId).then(version => {
      if (cancelled) return
      setSelected({ id: version.skill_id, name: version.package.name, project_id: projectId, created_at: version.created_at })
      setPreview(version)
    }).catch(error => { if (!cancelled) setError(errorMessage(error)) })
      .finally(() => { if (!cancelled) setBusy(false) })
    return () => { cancelled = true }
  }, [projectId, initialVersionId])
  const manifest = creating ? `---\nname: ${JSON.stringify(name.trim())}\ndescription: ${JSON.stringify(description.trim())}\n---\n${instructions}` : skillMd
  const canPublish = creating ? Boolean(name.trim() && description.trim() && instructions.trim()) : Boolean(skillMd.trim())

  const loadFiles = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true); setError(null)
    try { const parsed = await readSkillFiles(Array.from(files)); setSkillMd(parsed.skill_md); setResources(parsed.resources) }
    catch (err) { setError(errorMessage(err)) }
    finally { setBusy(false) }
  }
  const publish = async () => {
    setBusy(true); setError(null)
    try {
      const published = await importSkill(projectId, { version, skill_md: manifest, resources, required_tools: requiredTools.split(',').map(item => item.trim()).filter(Boolean) }, selected?.id)
      await Promise.all([queryClient.invalidateQueries({ queryKey: ['skills', projectId] }), queryClient.invalidateQueries({ queryKey: ['skill-versions', projectId] })])
      setSelected({ id: published.skill_id, name: published.name, project_id: projectId, created_at: published.created_at })
      setVersionOffset(0); setPreview(published); setImporting(false)
      toast.success('Skill version added to the Project catalog. Review it below to install.')
    } catch (err) { setError(errorMessage(err)) }
    finally { setBusy(false) }
  }
  const review = async (versionId: string) => {
    setBusy(true); setError(null)
    try { setPreview(await getSkillVersion(projectId, versionId)) }
    catch (err) { setError(errorMessage(err)) }
    finally { setBusy(false) }
  }
  const startImport = () => { setCreating(false); setImporting(true); setPreview(null); setSkillMd(''); setResources({}); setVersion('1.0.0'); setRequiredTools(''); setError(null) }
  const startCreate = () => { startImport(); setCreating(true); setName(''); setDescription(''); setInstructions('') }
  const back = () => { setImporting(false); setSelected(null); setPreview(null); setError(null) }

  return (
    <>
      <div className="space-y-5">
        <p className="text-sm text-muted">Create or import reusable procedures, review their versions and install them on Agents when needed.</p>
        {managerName && <p className="rounded-lg border border-border bg-background/40 p-3 text-xs text-muted">Installation updates the Agent draft and selects {managerName}. Use the editor’s Save action to persist it.</p>}
        {installDisabled && <p role="status" className="text-xs text-muted">Installation requires a compatible Context Manager. You can still create, import and review Skills.</p>}
        {error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">{error}</p>}
        {(selected || importing) && <Button variant="ghost" size="sm" disabled={busy} onClick={back}><ArrowLeft className="mr-2 h-4 w-4" />Project catalog</Button>}
        {importing ? (
          <div className="space-y-4">
            <h3 className="font-semibold">{selected ? `New version of ${selected.name}` : creating ? 'Create a Skill' : 'Import a Skill'}</h3>
            <p className="text-xs text-muted">{creating ? 'Describe when to use this Skill and write its instructions. Publish a fixed version to the Project catalog.' : <>Choose SKILL.md or a folder with SKILL.md and text files in references/ or assets/. Maximum 1 MB. Script execution is not supported.</>}</p>
            {!creating && <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" disabled={busy} onClick={() => fileInput.current?.click()}>Choose SKILL.md</Button>
              <Button variant="outline" size="sm" disabled={busy} onClick={() => folderInput.current?.click()}>Choose package folder</Button>
              <input ref={fileInput} type="file" accept=".md" className="hidden" aria-label="Import SKILL.md" onChange={event => { void loadFiles(event.target.files); event.target.value = '' }} />
              <input ref={folderInput} type="file" multiple {...directoryProps} className="hidden" aria-label="Import Skill folder" onChange={event => { void loadFiles(event.target.files); event.target.value = '' }} />
            </div>}
            <label className="block text-xs text-muted">Version<Input value={version} disabled={busy} placeholder="1.0.0" onChange={event => setVersion(event.target.value)} className="mt-1" /></label>
            {creating ? <div className="space-y-3">
              <label className="block text-xs text-muted">Name<Input value={name} disabled={busy} maxLength={64} placeholder="invoice-review" onChange={event => setName(event.target.value)} className="mt-1" /></label>
              <label className="block text-xs text-muted">When to use this Skill<Textarea value={description} disabled={busy} maxLength={1024} onChange={event => setDescription(event.target.value)} placeholder="Use when reviewing invoice totals before approval." className="mt-1" /></label>
              <label className="block text-xs text-muted">Instructions<Textarea value={instructions} disabled={busy} onChange={event => setInstructions(event.target.value)} className="mt-1 min-h-56 font-mono text-xs" placeholder="Explain the steps the Agent should follow…" /></label>
            </div> : <label className="block text-xs text-muted">SKILL.md<Textarea value={skillMd} disabled={busy} onChange={event => setSkillMd(event.target.value)} className="mt-1 min-h-56 font-mono text-xs" placeholder={'---\nname: your-skill\ndescription: When the Agent should use this Skill.\n---\nInstructions…'} /></label>}
            <label className="block text-xs text-muted">Required Tool names (optional, comma separated)<Input value={requiredTools} disabled={busy} onChange={event => setRequiredTools(event.target.value)} className="mt-1" placeholder="Use the names exposed to the Agent" /></label>
            <p className="text-xs text-muted">The Agent must already have these Tools available when it activates the Skill. Importing does not grant permissions.</p>
            {!!Object.keys(resources).length && <details className="text-xs text-muted"><summary>{Object.keys(resources).length} text resources included</summary><ul className="mt-2 space-y-1">{Object.keys(resources).map(path => <li key={path} className="font-mono">{path}</li>)}</ul></details>}
            <Button loading={busy} disabled={!canPublish || !/^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?$/.test(version)} onClick={() => void publish()}><Upload className="mr-2 h-4 w-4" />Publish version to catalog</Button>
          </div>
        ) : selected ? (
          <div className="grid gap-5 md:grid-cols-[220px_minmax(0,1fr)]">
            <div className="space-y-3">
              <h3 className="break-words font-semibold">{selected.name}</h3>
              <Button size="sm" variant="outline" onClick={startImport} disabled={busy}>Import new version</Button>
              {versions.isPending && <p role="status" className="text-xs text-muted">Loading versions…</p>}
              {versions.isError && <Button size="sm" variant="outline" onClick={() => void versions.refetch()}>Retry loading versions</Button>}
              {versions.data?.map(item => <button key={item.id} type="button" disabled={busy} onClick={() => void review(item.id)} aria-pressed={preview?.skill_version_id === item.id} className={`w-full rounded-lg border p-3 text-left text-xs ${preview?.skill_version_id === item.id ? 'border-primary bg-primary/10' : 'border-border hover:bg-accent'}`}><span className="block font-mono font-semibold">{item.version}</span><span className="mt-1 block text-muted">≈{item.estimated_instruction_units.toLocaleString()} instruction units</span>{bindings.some(binding => binding.skill_version_id === item.id) && <span className="mt-1 block text-primary-light">Installed in draft</span>}</button>)}
              <Pagination offset={versionOffset} count={versions.data?.length ?? 0} loading={versions.isFetching} onChange={setVersionOffset} />
            </div>
            {preview ? <div className="min-w-0 space-y-4">
              <div><h3 className="font-semibold">{preview.package.name} <span className="font-mono text-sm text-muted">{preview.version}</span></h3><p className="mt-2 text-sm text-muted">{preview.package.description}</p></div>
              {!!preview.package.required_tools.length && <p className="text-xs text-muted">Required Tools: {preview.package.required_tools.join(', ')}</p>}
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-background/50 p-4 font-mono text-xs leading-relaxed">{preview.package.skill_md}</pre>
              {Object.entries(preview.package.resources).map(([path, content]) => <details key={path} className="rounded-lg border border-border p-3 text-xs"><summary className="cursor-pointer break-all font-mono">{path}</summary><pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap">{content}</pre></details>)}
              <p className="break-all font-mono text-[10px] text-muted">SHA-256 {preview.package_hash}</p>
              <Button disabled={busy || installDisabled || !onInstall || bindings.some(item => item.skill_version_id === preview.skill_version_id && item.enabled)} onClick={() => onInstall?.(preview)}><Download className="mr-2 h-4 w-4" />{bindings.some(item => item.skill_id === preview.skill_id) ? 'Use this version' : 'Install on Agent'}</Button>
            </div> : <p className="py-12 text-center text-sm text-muted">Select a version to review its instructions and resources.</p>}
          </div>
        ) : <div className="space-y-4">
          <div className="flex flex-wrap gap-2"><Input aria-label="Search Project Skills" placeholder="Search Skills by name…" value={query} onChange={event => { setQuery(event.target.value); setOffset(0) }} className="min-w-48 flex-1" />{showCreateActions && <><Button variant="outline" onClick={startCreate}><Plus className="mr-2 h-4 w-4" />Create Skill</Button><Button variant="outline" onClick={startImport}><Upload className="mr-2 h-4 w-4" />Import Skill</Button></>}</div>
          {catalog.isPending && <p role="status" className="py-8 text-center text-sm text-muted">Loading Skills…</p>}
          {catalog.isError && <div role="alert" className="text-sm text-muted">Could not load the catalog. <Button size="sm" variant="outline" onClick={() => void catalog.refetch()}>Retry</Button></div>}
          {!catalog.isError && !catalog.isPending && catalog.data?.length === 0 && <div className="rounded-xl border border-dashed border-border px-6 py-10 text-center"><h3 className="text-sm font-medium">{query ? 'No matching Skills' : 'Build your Agent’s skill set'}</h3><p className="mt-2 text-xs text-muted">{query ? 'Try another name or import a Skill.' : 'Import a reusable procedure, then install the version your Agent should use.'}</p></div>}
          <div className="divide-y divide-border rounded-lg border border-border">{catalog.data?.map(skill => <button key={skill.id} type="button" onClick={() => { setSelected(skill); setPreview(null); setVersionOffset(0) }} className="flex w-full items-center justify-between gap-3 p-4 text-left hover:bg-accent/40"><span className="min-w-0 break-words text-sm font-medium">{skill.name}</span><span className="shrink-0 text-xs text-muted">{bindings.some(item => item.skill_id === skill.id) ? 'Installed · Versions' : 'View versions'}</span></button>)}</div>
          <Pagination offset={offset} count={catalog.data?.length ?? 0} loading={catalog.isFetching} onChange={setOffset} />
        </div>}
      </div>
    </>
  )
}
function Pagination({ offset, count, loading, onChange }: { offset: number; count: number; loading: boolean; onChange: (offset: number) => void }) {
  if (!offset && count < 20) return null
  return <div className="flex items-center gap-2"><Button size="sm" variant="ghost" disabled={!offset || loading} onClick={() => onChange(Math.max(0, offset - 20))}>Previous</Button><span className="text-xs text-muted">Page {offset / 20 + 1}</span><Button size="sm" variant="ghost" disabled={count < 20 || loading} onClick={() => onChange(offset + 20)}>Next</Button></div>
}
