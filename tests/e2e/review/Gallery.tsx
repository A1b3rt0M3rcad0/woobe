import { Component, useState, type ReactNode } from 'react'
import { BrowserRouter } from 'react-router-dom'
import { AppProviders } from '../../../packages/woobe-frontend/src/app/providers'
import { AgentEditorProvider } from '../../../packages/woobe-frontend/src/features/playground/AgentEditorContext'
import { commonProps, productionAgent, project } from './fixtures'
import { overlayCases } from './registry'
import { Primitives } from './Primitives'
import './review.css'

class ReviewBoundary extends Component<{ children: ReactNode }, { message: string }> {
  state = { message: '' }
  static getDerivedStateFromError(error: Error) { return { message: error.message } }
  render() { return this.state.message ? <pre data-review-error>{this.state.message}</pre> : this.props.children }
}

export function Gallery() {
  const name = new URLSearchParams(location.search).get('case') ?? 'primitives'
  const [open, setOpen] = useState(true)
  const close = () => setOpen(false)
  const record = overlayCases.find(item => item.id === name)
  const callbacks = Object.fromEntries(['onClose','onConfirm','onSubmit','onApply','onSaved','onCreated','onUploaded','onSelect','onReload','onStay','onDiscard','onSave','onAdd','onCreate','onStage','onPublish','onViewVersion','onActivate','onUseModel','onImport','onUseSnapshot','onDeploy','onEnvironmentChange','onCredentialCreated','onRotated'].map(key => [key, key === 'onClose' ? close : async () => {}]))
  return <BrowserRouter><AppProviders><AgentEditorProvider agent={productionAgent} projectId={project.id}>
    <main className="review-shell" data-review-ready data-review-case={name}>
      <header className="review-caption"><span>Woobe component review</span><span>Synthetic API data · {name}</span></header>
      <ReviewBoundary>
        {name === 'primitives' ? <Primitives /> : record && open ? <div style={name.includes('Popover') ? { display: 'flex', justifyContent: 'flex-end' } : undefined}><record.component {...commonProps} {...callbacks} {...record.props} /></div> : <p data-review-closed>Closed</p>}
      </ReviewBoundary>
    </main>
  </AgentEditorProvider></AppProviders></BrowserRouter>
}
