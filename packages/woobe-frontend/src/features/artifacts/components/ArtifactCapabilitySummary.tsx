function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

export function artifactCapabilityFromRuntimeConfig(value: unknown) {
  return record(record(value).artifacts)
}

export function ArtifactCapabilitySummary({ runtimeConfig, label = 'Artifacts' }: { runtimeConfig: unknown; label?: string }) {
  const capability = artifactCapabilityFromRuntimeConfig(runtimeConfig)
  if (capability.enabled !== true) {
    return <section className="rounded-technical border border-border/75 bg-background/30 p-ui-md"><h3 className="font-mono text-system-meta font-medium uppercase tracking-wide text-muted">{label}</h3><p className="mt-ui-xs text-product-small text-muted-foreground">Disabled in this configuration snapshot.</p></section>
  }
  const binding = record(capability.workspace_binding)
  const limits = record(capability.limits)
  const profile = record(capability.processing_profile)
  const actions = Array.isArray(capability.actions) ? capability.actions.filter((item): item is string => typeof item === 'string') : []
  return (
    <section className="min-w-0 rounded-technical border border-primary/20 bg-primary/5 p-ui-md">
      <h3 className="font-mono text-system-meta font-medium uppercase tracking-wide text-primary-light">{label}</h3>
      <dl className="mt-ui-sm grid min-w-0 gap-ui-sm text-product-small sm:grid-cols-2">
        <div className="min-w-0"><dt className="text-muted-foreground">Workspace selector</dt><dd className="break-all font-mono">{String(binding.field ?? 'Unavailable')} · {String(binding.scope ?? 'unknown')}</dd></div>
        <div className="min-w-0"><dt className="text-muted-foreground">Namespace</dt><dd className="break-all">{String(binding.namespace ?? 'Unavailable')}</dd></div>
        <div className="min-w-0"><dt className="text-muted-foreground">Actions in snapshot</dt><dd className="break-words">{actions.join(', ') || 'None'}</dd></div>
        <div className="min-w-0"><dt className="text-muted-foreground">Read budgets</dt><dd className="break-words">{String(limits.max_read_chars ?? '—')} chars/read · {String(limits.max_total_read_chars ?? '—')} total · {String(limits.max_context_units ?? '—')} units</dd></div>
        <div className="min-w-0"><dt className="text-muted-foreground">Processing profile</dt><dd className="break-all font-mono">{profile.ref ? `${String(profile.ref)} r${String(profile.revision ?? 1)}` : 'Workspace default'}</dd></div>
      </dl>
      <p className="mt-ui-sm text-system-meta text-muted-foreground">This is the pinned configuration policy. The server still evaluates current Project and Workspace grants for every operation.</p>
    </section>
  )
}
