import { useState } from 'react'
import { Bot, Search } from 'lucide-react'
import * as UI from '@woobe/ui'

export function Primitives() {
  const [filter, setFilter] = useState('draft')
  const [query, setQuery] = useState('')
  const [date, setDate] = useState(new Date('2026-10-20T12:00:00Z'))
  return <div className="review-grid">
    <section className="review-sample" data-sample="brand"><h2>Woobe identity</h2><div className="review-stack"><UI.WoobeLogo /><UI.WoobeLogo variant="mark" /></div><div className="woobe-navigation mt-4 rounded-container bg-surface p-4"><UI.WoobeLogo /></div></section>
    <section className="review-sample review-wide" data-sample="fonts"><h2>Self-hosted typefaces</h2>
      <p data-font-probe="mono" className="font-mono font-medium">Usage Cap · PR Reviewer · $312.40 / $380 · 0123456789 · I l 1 O 0 · ação conexão utilização</p>
      <p data-font-probe="sans" className="font-sans font-normal">Informação, configuração e observação: texto explicativo em Inter.</p>
    </section>
    <section className="review-sample" data-sample="contribution-bars"><h2>Context contributions</h2><UI.ContributionBars unit="Persisted contribution units" rows={[{ id: 'system', label: 'System instructions', value: 1898, share: 1898/1899 }, { id: 'input', label: 'Current input', value: 1, share: 1/1899 }]} /></section>
    <section className="review-sample" data-sample="buttons"><h2>Buttons and states</h2><div className="review-stack">
      {(['default','secondary','outline','ghost','destructive','link'] as const).map(variant => <UI.Button key={variant} variant={variant}>{variant}</UI.Button>)}
      <UI.Button disabled>Disabled</UI.Button><UI.Button loading>Saving</UI.Button>
      {(['xs','technical','sm','lg','icon','iconSm','iconXs'] as const).map(size => <UI.Button key={size} size={size} aria-label={`Size ${size}`}><Bot size={14} /></UI.Button>)}
    </div></section>
    <section className="review-sample" data-sample="badges"><h2>State and identity</h2><div className="review-stack">
      {(['default','secondary','outline','success','warning','destructive','network'] as const).map(variant => <UI.Badge key={variant} variant={variant}>{variant}</UI.Badge>)}
      <UI.ResourcePill tone="success">Production enabled</UI.ResourcePill>
    </div><UI.Separator className="my-4" /><UI.TechnicalListItem label="Review agent" description="Exact release 1.2.0" trailing={<UI.Badge variant="success">Completed</UI.Badge>} /></section>
    <section className="review-sample" data-sample="fields"><h2>Forms</h2><div className="review-fields">
      <UI.Field><UI.FieldLabel htmlFor="review-name">Agent name <UI.FieldOptional /></UI.FieldLabel><UI.Input id="review-name" defaultValue="PR Reviewer" /><UI.FieldDescription>Identifies the Agent in this Project.</UI.FieldDescription></UI.Field>
      <UI.Field><UI.FieldLabel htmlFor="review-error">Required value</UI.FieldLabel><UI.Input id="review-error" invalid /><UI.FieldError>Enter a value.</UI.FieldError></UI.Field>
      <UI.Input aria-label="Disabled input" disabled value="Read only during save" />
      <UI.InputGroup start={<Search size={16} />}><UI.Input aria-label="Search input" placeholder="Search resources" /></UI.InputGroup>
      <UI.Select aria-label="Environment" value={filter} onChange={event=>setFilter(event.target.value)} options={[{value:'draft',label:'Draft'},{value:'production',label:'Production'}]} />
      <UI.Textarea aria-label="Objective" defaultValue="Resolve support requests accurately." />
      <label><UI.Checkbox defaultChecked /> Allow execution</label>
      <UI.ReadOnlyField label="Release" value="1.2.0" />
      <UI.FormActions><UI.Button variant="outline">Cancel</UI.Button><UI.Button>Save</UI.Button></UI.FormActions>
    </div></section>
    <section className="review-sample" data-sample="panels"><h2>Technical windows</h2>
      <UI.DotMeter value={82.21} label="Share of known spend" /><UI.DotMeter value={null} label="Pricing coverage" />
      <UI.SectionBlock title="Context policy" description="A production section uses the same technical hierarchy."><UI.PanelHeader title="Runtime context" hierarchy="technical" /></UI.SectionBlock>
      <UI.Card><UI.CardHeader><UI.CardTitle>Review configuration</UI.CardTitle><UI.CardDescription>Prose uses Inter, technical values use JetBrains Mono.</UI.CardDescription></UI.CardHeader><UI.CardContent><UI.MetricTile label="Known runtime cost · USD" value="$312.40" detail="Synthetic fixture · October 2026" /></UI.CardContent><UI.CardFooter>Updated 12:00 UTC</UI.CardFooter></UI.Card>
      <UI.ResourceCard icon={<Bot size={18}/>} title="PR Reviewer" subtitle="Support review model" metadata={<UI.Badge variant="success">Production enabled</UI.Badge>} footer="Release 1.2.0 · updated 12:00 UTC" />
      <UI.CreateResourceCard title="Create Agent" description="Define a new Agent" icon={<Bot size={16}/>} />
    </section>
    <section className="review-sample review-wide" data-sample="tables"><h2>Tables, tabs and filters</h2>
      <UI.PageHeader title="Project resources" description="Synthetic data rendered by the production primitives." />
      <UI.ResourceToolbar><UI.ResourceTabs label="Environment filter" value={filter} onChange={setFilter} tabs={[{value:'draft',label:'Draft',count:2},{value:'production',label:'Production',count:1}]} /><UI.ResourceSearch value={query} onChange={setQuery} label="Find resources" placeholder="Search resources" /></UI.ResourceToolbar>
      <UI.Tabs tabs={[{id:'agents',label:'Agents',content:<UI.Table keyExtractor={row=>row.id} data={[{id:'agent-one',name:'PR Reviewer',status:'Active',cost:'$2.14'},{id:'agent-two',name:'Support Agent',status:'Inactive',cost:'Unknown'}]} columns={[{key:'name',header:'Agent'},{key:'status',header:'Status'},{key:'cost',header:'Known cost (USD)',className:'text-right'}]}/>},{id:'networks',label:'Networks',content:'No Networks in this fixture.'}]} />
      <UI.Stepper items={[{id:'identity',label:'Identity',state:'complete'},{id:'model',label:'Model',state:'current'},{id:'review',label:'Review',state:'pending'}]} />
    </section>
    <section className="review-sample" data-sample="feedback"><h2>Feedback and loading</h2>
      {(['default','success','warning','destructive'] as const).map(variant=><UI.Alert key={variant} variant={variant}><UI.AlertTitle>{variant}</UI.AlertTitle><UI.AlertDescription>Operation status remains explicit and readable.</UI.AlertDescription></UI.Alert>)}
      <UI.Skeleton className="h-12 w-full" /><UI.LoadingState message="Loading resources" />
      <UI.EmptyStatePanel title="No Runs in this period" description="Choose another period to inspect activity." />
      <UI.GuidedEmptyState title="Create your first Agent" description="Connect a model and define an objective." actionLabel="Create Agent" onAction={()=>{}} />
    </section>
    <section className="review-sample" data-sample="code"><h2>Code and copy</h2>
      <UI.CodePanel title="Runtime configuration"><UI.JsonCodeBlock value={{environment:'production',agent_id:'demo-agent',enabled:true}} /></UI.CodePanel>
      <UI.CopyButton text="demo-agent" /><UI.JsonEditor value={'{"name":"PR Reviewer"}'} onChange={()=>{}} />
      <UI.MathSurface display><span>312.40 / 380.00 = 82.21%</span></UI.MathSurface>
    </section>
    <section className="review-sample" data-sample="dates"><h2>Date and time controls</h2><UI.WoobeDatePicker value={date} minDate={new Date('2026-10-01T00:00:00Z')} onChange={setDate} /><UI.WoobeDateTimePicker value={date} minDate={new Date('2026-10-01T00:00:00Z')} onChange={setDate} /></section>
    <section className="review-sample review-wide" data-sample="resource-shell"><h2>Resource shell and scrolling</h2>
      <UI.ResourcePage title="Review resources" description="Shared resource page shell with operational density.">
        <UI.ScrollArea className="h-32" tabIndex={0} aria-label="Release history">{['1.2.0','1.1.0','1.0.0','0.9.0'].map(version=><UI.TechnicalListItem key={version} label={`Release ${version}`} description="Immutable snapshot" />)}</UI.ScrollArea>
        <UI.ResourceEmptyState title="No matching resources" description="Adjust the search." />
      </UI.ResourcePage>
    </section>
    <section className="review-sample" data-sample="dropdown"><h2>Dropdown</h2><UI.Dropdown trigger={<UI.Button variant="outline">Open actions</UI.Button>}><UI.Button variant="ghost">Inspect release</UI.Button><UI.Button variant="ghost">Open settings</UI.Button></UI.Dropdown></section>
  </div>
}
