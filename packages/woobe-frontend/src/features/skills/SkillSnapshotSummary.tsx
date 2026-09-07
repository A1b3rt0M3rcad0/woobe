import { skillsConfig } from './config'
export function SkillSnapshotSummary({ runtimeConfig }: { runtimeConfig: unknown }) {
  const config = skillsConfig(runtimeConfig)
  if (!config.bindings.length) return null
  return <section className="rounded-xl border border-border bg-background/35 p-3">
    <p className="text-xs font-semibold text-muted">Skills · Fixed versions</p>
    <ul className="mt-2 space-y-2">{config.bindings.map(binding => {
      const snapshot = config.snapshots.find(item => item.skill_version_id === binding.skill_version_id)
      return <li key={binding.skill_id} className="text-xs"><span className="break-words">{snapshot?.package.name ?? binding.skill_id} · {snapshot?.version ?? binding.skill_version_id}</span><span className="ml-2 text-muted">{binding.enabled ? 'Enabled' : 'Disabled'}</span>{snapshot?.package_hash && <p className="mt-0.5 break-all font-mono text-[9px] text-muted">SHA-256 {snapshot.package_hash}</p>}</li>
    })}</ul>
  </section>
}
