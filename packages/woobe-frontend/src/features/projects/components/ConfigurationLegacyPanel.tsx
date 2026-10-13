import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button, Dialog } from '@woobe/ui'
import { convertLegacyConfiguration, listLegacyConfiguration, type LegacyConfigurationBinding } from '../configuration'
import type { ProjectEnvironment } from '../types'

export function ConfigurationLegacyPanel({ projectId, environment, canConvert, onSaved }: { projectId: string; environment: ProjectEnvironment; canConvert: boolean; onSaved: () => void }) {
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<LegacyConfigurationBinding | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const query = useQuery({ queryKey: ['project-configuration-legacy', projectId, environment, offset], queryFn: () => listLegacyConfiguration(projectId, environment, offset), retry: false })
  const convert = async () => {
    if (!selected) return
    setPending(true); setError('')
    try { await convertLegacyConfiguration(projectId, environment, selected); setSelected(null); onSaved(); void query.refetch() }
    catch { setError('Conversion was not confirmed. Refresh metadata and check migration and value-write permissions.') }
    finally { setPending(false) }
  }
  if (query.isPending) return <p role="status">Loading legacy mappings…</p>
  if (query.isError) return <p role="alert">Legacy configuration is unavailable or restricted.</p>
  return <div className="space-y-ui-md">
    <p className="text-product-small text-muted-foreground">Explicit legacy routes keep their original material until you review each environment. Conversion does not reveal the value.</p>
    <div className="overflow-x-auto rounded-technical border border-border bg-card"><table className="w-full text-left text-product-small"><thead><tr>{['Key', 'Consumer', 'Source', 'Material', 'Action'].map(label => <th key={label} className="p-ui-md">{label}</th>)}</tr></thead>
      <tbody>{query.data.items.map(item => <tr key={item.id} className="border-t border-border"><td className="p-ui-md font-mono">{item.key}</td><td className="p-ui-md">{item.source_kind}</td><td className="p-ui-md">{item.source}</td><td className="p-ui-md">{item.material}</td><td className="p-ui-md">{canConvert && item.source === 'legacy_compat' && <Button size="sm" variant="outline" disabled={item.material !== 'present'} onClick={() => setSelected(item)}>Convert {environment}</Button>}</td></tr>)}</tbody></table>
      {!query.data.items.length && <p className="p-ui-lg">No centralized legacy mappings.</p>}
    </div>
    <div className="flex justify-end gap-ui-sm"><Button variant="outline" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</Button><Button variant="outline" disabled={offset + 50 >= query.data.total} onClick={() => setOffset(offset + 50)}>Next</Button></div>
    {selected && <Dialog open onClose={() => { if (!pending) setSelected(null) }} title={`Convert ${selected.key} · ${environment}`}><div className="space-y-ui-md p-ui-lg"><p>The current legacy value will become the value for {environment}. Review the consumer’s destination approval before using it. Other environments keep their explicit routes.</p>{error && <p role="alert">{error}</p>}<div className="flex justify-end gap-ui-sm"><Button variant="outline" disabled={pending} onClick={() => setSelected(null)}>Cancel</Button><Button disabled={pending} onClick={() => void convert()}>Confirm conversion</Button></div></div></Dialog>}
  </div>
}
