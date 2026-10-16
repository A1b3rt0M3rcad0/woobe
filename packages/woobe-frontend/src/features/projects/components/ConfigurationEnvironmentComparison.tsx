import { useEffect, useState } from 'react'
import { Button } from '@woobe/ui'
import { useQueries } from '@tanstack/react-query'
import { listConfiguration } from '../configuration'
import type { ProjectEnvironment } from '../types'

const environments: ProjectEnvironment[] = ['draft', 'staging', 'production']
export function ConfigurationEnvironmentComparison({ projectId, search }: { projectId: string; search: string }) {
  const [offset, setOffset] = useState(0)
  useEffect(() => setOffset(0), [projectId, search])
  const queries = useQueries({ queries: environments.map(environment => ({ queryKey: ['project-configuration', projectId, environment, search, 'all', offset], queryFn: () => listConfiguration(projectId, environment, search, 'all', offset), retry: false })) })
  const keys = new Map(queries.flatMap(query => query.data?.items ?? []).map(key => [key.id, key]))
  return <><div className="overflow-x-auto rounded-technical border border-border bg-card"><table className="w-full text-left text-product-small">
    <thead><tr><th className="p-ui-md">Key</th>{environments.map(environment => <th className="p-ui-md capitalize" key={environment}>{environment}</th>)}</tr></thead>
    <tbody>{Array.from(keys.values()).map(key => <tr key={key.id} className="border-t border-border"><td className="p-ui-md font-mono">{key.key}</td>
      {queries.map((query, index) => {
        const item = query.data?.items.find(item => item.id === key.id)
        return <td className="p-ui-md" key={environments[index]}>{query.isPending ? 'Loading…' : query.isError ? 'Unavailable or restricted' : item ? <>
          <p>{item.material === 'present' ? 'Value saved' : item.material === 'missing' ? 'Not set' : item.material.replaceAll('_', ' ')}</p>
          {item.approval && <p className="text-product-caption text-muted-foreground">{item.approval.state === 'approved' ? 'Use approved' : item.approval.state === 'approval_required' ? 'Approval required' : 'No connections yet'}</p>}
        </> : 'Not on this page'}</td>
      })}
    </tr>)}</tbody></table>
    {!keys.size && <p className="p-ui-lg text-muted-foreground">No accessible configuration keys on this page.</p>}
  </div><div className="flex justify-end gap-ui-sm"><Button variant="outline" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</Button><Button variant="outline" disabled={!queries.some(query => query.data?.has_next)} onClick={() => setOffset(offset + 50)}>Next</Button></div></>
}
