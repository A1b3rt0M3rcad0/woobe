import { type ReactNode, useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { DEFAULT_CHAT_SURFACE_APPEARANCE } from '@/features/chat-surfaces/appearance'
import type {
  ChatSurfaceAppearance,
  ChatSurfaceMessageStyle,
} from '@/features/chat-surfaces/types'
import { cn } from '@/lib/utils'

export type ChatSurfaceAppearanceSection =
  | 'general'
  | 'header'
  | 'surface'
  | 'messages'
  | 'composer'
  | 'send-button'
  | 'activity'

interface ChatSurfaceAppearanceEditorProps {
  appearance: ChatSurfaceAppearance
  section: ChatSurfaceAppearanceSection
  disabled?: boolean
  onChange: (appearance: ChatSurfaceAppearance) => void
}

const selectClassName = 'h-[34px] w-full min-w-0 rounded-control border border-border bg-control px-3 font-mono text-[10px] text-slate-100 outline-none transition-colors hover:border-slate-600 focus:border-primary focus:ring-1 focus:ring-primary/30 disabled:opacity-60'

type MessageRole = keyof ChatSurfaceAppearance['messages']

function SettingPanel({
  title,
  description,
  action,
  children,
}: {
  title: string
  description: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="min-w-0 overflow-hidden rounded-container border border-border bg-surface/[0.92]">
      <div className="flex flex-col gap-3 border-b border-border px-4 py-3.5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="font-mono text-[11px] font-bold text-slate-50">{title}</h3>
          <p className="mt-1 max-w-2xl font-sans text-[11px] leading-5 text-muted-foreground">{description}</p>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      <div className="min-w-0 px-4">{children}</div>
    </section>
  )
}

function SubsectionTitle({ title, description }: { title: string; description?: string }) {
  return (
    <div className="border-b border-border/70 pb-2.5 pt-4 first:pt-3.5">
      <p className="font-mono text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-200">{title}</p>
      {description ? <p className="mt-1 font-sans text-[10px] leading-4 text-muted-foreground">{description}</p> : null}
    </div>
  )
}

function SettingRow({
  label,
  description,
  children,
  align = 'center',
}: {
  label: string
  description?: string
  children: ReactNode
  align?: 'center' | 'start'
}) {
  return (
    <div
      className={cn(
        'grid min-w-0 gap-3 border-b border-border/60 py-3.5 last:border-b-0 md:grid-cols-[minmax(0,1fr)_minmax(220px,290px)]',
        align === 'center' ? 'md:items-center' : 'md:items-start',
      )}
    >
      <div className="min-w-0">
        <p className="font-mono text-[10px] font-medium text-slate-100">{label}</p>
        {description ? <p className="mt-1 max-w-xl font-sans text-[10px] leading-4 text-muted-foreground">{description}</p> : null}
      </div>
      <div className="min-w-0 md:w-full md:justify-self-end">{children}</div>
    </div>
  )
}

function OptionalColorControl({
  value,
  fallback,
  disabled,
  onChange,
}: {
  value: string | null
  fallback: string
  disabled?: boolean
  onChange: (value: string | null) => void
}) {
  const customized = value !== null

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2 md:justify-end">
      <input
        type="color"
        value={value ?? fallback}
        disabled={disabled || !customized}
        onChange={(event) => onChange(event.target.value.toUpperCase())}
        className="h-8 w-9 shrink-0 rounded-control border border-border bg-control p-1 disabled:opacity-45"
        aria-label="Select color"
      />
      <code className="min-w-[72px] truncate font-mono text-[9px] text-muted-foreground">
        {value ?? 'Theme'}
      </code>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="shrink-0"
        disabled={disabled}
        onClick={() => onChange(customized ? null : fallback.toUpperCase())}
      >
        {customized ? 'Reset' : 'Customize'}
      </Button>
    </div>
  )
}

function PrimaryColorControl({
  value,
  disabled,
  onChange,
}: {
  value: string
  disabled?: boolean
  onChange: (value: string) => void
}) {
  return (
    <div className="flex min-w-0 items-center gap-2 md:justify-end">
      <input
        type="color"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value.toUpperCase())}
        className="h-8 w-9 shrink-0 rounded-control border border-border bg-control p-1 disabled:opacity-60"
        aria-label="Select primary color"
      />
      <code className="min-w-0 truncate font-mono text-[9px] text-muted-foreground">{value}</code>
    </div>
  )
}

function NumberControl({
  value,
  min,
  max,
  suffix,
  disabled,
  onChange,
}: {
  value: number
  min: number
  max: number
  suffix?: string
  disabled?: boolean
  onChange: (value: number) => void
}) {
  return (
    <div className="flex min-w-0 items-center gap-2 md:justify-end">
      <Input
        type="number"
        min={min}
        max={max}
        value={value}
        disabled={disabled}
        className="w-24 shrink-0 font-mono text-[10px]"
        onChange={(event) => {
          const next = Number(event.target.value)
          if (Number.isFinite(next)) onChange(next)
        }}
      />
      {suffix ? <span className="w-8 shrink-0 font-mono text-[9px] text-muted-foreground">{suffix}</span> : null}
    </div>
  )
}

function ToggleControl({
  checked,
  label,
  disabled,
  onChange,
}: {
  checked: boolean
  label: string
  disabled?: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <label className="flex min-w-0 items-center gap-2 font-mono text-[10px] text-slate-200 md:justify-end">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="h-3.5 w-3.5 rounded-technical border-border bg-control accent-primary"
      />
      <span className="truncate">{label}</span>
    </label>
  )
}

function MessageRoleSelector({ value, onChange }: { value: MessageRole; onChange: (value: MessageRole) => void }) {
  const roles: Array<{ id: MessageRole; label: string }> = [
    { id: 'user', label: 'User' },
    { id: 'assistant', label: 'Assistant' },
    { id: 'system', label: 'System' },
  ]

  return (
    <div className="inline-flex max-w-full rounded-control border border-border bg-control p-[3px]">
      {roles.map((role) => (
        <button
          key={role.id}
          type="button"
          onClick={() => onChange(role.id)}
          className={cn(
            'flex h-[27px] items-center rounded-technical border px-2.5 font-mono text-[9px] font-medium transition-colors',
            value === role.id
              ? 'border-primary/35 bg-primary/[0.12] text-slate-50'
              : 'border-transparent text-muted-foreground hover:bg-accent/45 hover:text-slate-200',
          )}
        >
          {role.label}
        </button>
      ))}
    </div>
  )
}

function MessageRows({
  value,
  primaryColor,
  disabled,
  onChange,
}: {
  value: ChatSurfaceMessageStyle
  primaryColor: string
  disabled?: boolean
  onChange: (value: ChatSurfaceMessageStyle) => void
}) {
  return (
    <>
      <SettingRow label="Background" description="Bubble background color.">
        <OptionalColorControl value={value.background_color} fallback={primaryColor} disabled={disabled} onChange={(background_color) => onChange({ ...value, background_color })} />
      </SettingRow>
      <SettingRow label="Text color" description="Foreground color used by message content.">
        <OptionalColorControl value={value.text_color} fallback="#FFFFFF" disabled={disabled} onChange={(text_color) => onChange({ ...value, text_color })} />
      </SettingRow>
      <SettingRow label="Border color" description="Optional outline color for the message bubble.">
        <OptionalColorControl value={value.border_color} fallback="#1E293B" disabled={disabled} onChange={(border_color) => onChange({ ...value, border_color })} />
      </SettingRow>
      <SettingRow label="Border width"><NumberControl value={value.border_width} min={0} max={4} suffix="px" disabled={disabled} onChange={(border_width) => onChange({ ...value, border_width })} /></SettingRow>
      <SettingRow label="Radius"><NumberControl value={value.border_radius} min={0} max={32} suffix="px" disabled={disabled} onChange={(border_radius) => onChange({ ...value, border_radius })} /></SettingRow>
      <SettingRow label="Maximum width" description="Maximum bubble width relative to the conversation area."><NumberControl value={value.max_width} min={40} max={100} suffix="%" disabled={disabled} onChange={(max_width) => onChange({ ...value, max_width })} /></SettingRow>
      <SettingRow label="Vertical padding"><NumberControl value={value.padding_y} min={4} max={24} suffix="px" disabled={disabled} onChange={(padding_y) => onChange({ ...value, padding_y })} /></SettingRow>
      <SettingRow label="Horizontal padding"><NumberControl value={value.padding_x} min={6} max={32} suffix="px" disabled={disabled} onChange={(padding_x) => onChange({ ...value, padding_x })} /></SettingRow>
      <SettingRow label="Avatar" description="Show a role marker alongside this message type."><ToggleControl checked={value.show_avatar} label="Show role avatar" disabled={disabled} onChange={(show_avatar) => onChange({ ...value, show_avatar })} /></SettingRow>
    </>
  )
}

export function ChatSurfaceAppearanceEditor({ appearance, section, disabled, onChange }: ChatSurfaceAppearanceEditorProps) {
  const [messageRole, setMessageRole] = useState<MessageRole>('user')

  const update = <K extends keyof ChatSurfaceAppearance>(key: K, value: ChatSurfaceAppearance[K]) => onChange({ ...appearance, [key]: value })

  const resetSection = () => {
    if (disabled) return
    if (section === 'general') {
      onChange({
        ...appearance,
        theme: DEFAULT_CHAT_SURFACE_APPEARANCE.theme,
        primary_color: DEFAULT_CHAT_SURFACE_APPEARANCE.primary_color,
        title: DEFAULT_CHAT_SURFACE_APPEARANCE.title,
        placeholder: DEFAULT_CHAT_SURFACE_APPEARANCE.placeholder,
        welcome_message: DEFAULT_CHAT_SURFACE_APPEARANCE.welcome_message,
      })
      return
    }
    if (section === 'header') {
      update('header', { ...DEFAULT_CHAT_SURFACE_APPEARANCE.header })
      return
    }
    if (section === 'surface') {
      onChange({
        ...appearance,
        surface: { ...DEFAULT_CHAT_SURFACE_APPEARANCE.surface },
        conversation: { ...DEFAULT_CHAT_SURFACE_APPEARANCE.conversation },
      })
      return
    }
    if (section === 'messages') {
      update('messages', { ...appearance.messages, [messageRole]: { ...DEFAULT_CHAT_SURFACE_APPEARANCE.messages[messageRole] } })
      return
    }
    if (section === 'composer') {
      onChange({
        ...appearance,
        composer: { ...DEFAULT_CHAT_SURFACE_APPEARANCE.composer },
        input: { ...DEFAULT_CHAT_SURFACE_APPEARANCE.input },
      })
      return
    }
    if (section === 'send-button') {
      update('send_button', { ...DEFAULT_CHAT_SURFACE_APPEARANCE.send_button })
      return
    }
    onChange({
      ...appearance,
      activity: { ...DEFAULT_CHAT_SURFACE_APPEARANCE.activity, labels: { ...DEFAULT_CHAT_SURFACE_APPEARANCE.activity.labels } },
      response: { ...DEFAULT_CHAT_SURFACE_APPEARANCE.response },
    })
  }

  const resetLabel = section === 'messages' ? `Reset ${messageRole}` : 'Reset section'
  const resetAction = <Button type="button" size="sm" variant="outline" disabled={disabled} onClick={resetSection}>{resetLabel}</Button>

  if (section === 'general') {
    return (
      <SettingPanel title="General appearance" description="Identity, base theme and the initial conversation copy." action={resetAction}>
        <SettingRow label="Display title" description="Title rendered in the ChatSurface header when the header is enabled."><Input value={appearance.title} disabled={disabled} maxLength={80} onChange={(event) => update('title', event.target.value)} /></SettingRow>
        <SettingRow label="Theme" description="Base color system used when a component does not override a color.">
          <select value={appearance.theme} disabled={disabled} onChange={(event) => update('theme', event.target.value as ChatSurfaceAppearance['theme'])} className={selectClassName}>
            <option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option>
          </select>
        </SettingRow>
        <SettingRow label="Primary color" description="Primary accent used by default for actions, focus and user messages."><PrimaryColorControl value={appearance.primary_color} disabled={disabled} onChange={(primary_color) => update('primary_color', primary_color)} /></SettingRow>
        <SettingRow label="Placeholder" description="Text shown in the composer before the user types a message."><Input value={appearance.placeholder} disabled={disabled} maxLength={120} onChange={(event) => update('placeholder', event.target.value)} /></SettingRow>
        <SettingRow label="Welcome message" description="Optional initial message shown before the first user message." align="start"><Textarea value={appearance.welcome_message ?? ''} disabled={disabled} rows={3} maxLength={500} onChange={(event) => update('welcome_message', event.target.value)} /></SettingRow>
      </SettingPanel>
    )
  }

  if (section === 'header') {
    return (
      <SettingPanel title="Header" description="Control the top bar independently from the rest of the conversation." action={resetAction}>
        <SettingRow label="Visibility" description="Hide the complete top bar when the integrator provides its own surrounding UI."><ToggleControl checked={appearance.header.visible} label="Show header" disabled={disabled} onChange={(visible) => update('header', { ...appearance.header, visible })} /></SettingRow>
        <SettingRow label="Background"><OptionalColorControl value={appearance.header.background_color} fallback="#0F1729" disabled={disabled} onChange={(background_color) => update('header', { ...appearance.header, background_color })} /></SettingRow>
        <SettingRow label="Text color"><OptionalColorControl value={appearance.header.text_color} fallback="#F8FAFC" disabled={disabled} onChange={(text_color) => update('header', { ...appearance.header, text_color })} /></SettingRow>
        <SettingRow label="Border color"><OptionalColorControl value={appearance.header.border_color} fallback="#1E293B" disabled={disabled} onChange={(border_color) => update('header', { ...appearance.header, border_color })} /></SettingRow>
        <SettingRow label="Border width"><NumberControl value={appearance.header.border_width} min={0} max={4} suffix="px" disabled={disabled} onChange={(border_width) => update('header', { ...appearance.header, border_width })} /></SettingRow>
        <SettingRow label="Height"><NumberControl value={appearance.header.height} min={40} max={96} suffix="px" disabled={disabled} onChange={(height) => update('header', { ...appearance.header, height })} /></SettingRow>
        <SettingRow label="Horizontal padding"><NumberControl value={appearance.header.padding} min={0} max={40} suffix="px" disabled={disabled} onChange={(padding) => update('header', { ...appearance.header, padding })} /></SettingRow>
        <SettingRow label="Alignment" description="Horizontal placement of the header title.">
          <select value={appearance.header.alignment} disabled={disabled} onChange={(event) => update('header', { ...appearance.header, alignment: event.target.value as ChatSurfaceAppearance['header']['alignment'] })} className={selectClassName}>
            <option value="left">Left</option><option value="center">Center</option><option value="right">Right</option>
          </select>
        </SettingRow>
      </SettingPanel>
    )
  }

  if (section === 'surface') {
    return (
      <SettingPanel title="Surface and conversation" description="Configure the outer ChatSurface shell and the scrolling message area." action={resetAction}>
        <SubsectionTitle title="Surface" description="Outer boundary of the embedded ChatSurface." />
        <SettingRow label="Background"><OptionalColorControl value={appearance.surface.background_color} fallback="#020817" disabled={disabled} onChange={(background_color) => update('surface', { ...appearance.surface, background_color })} /></SettingRow>
        <SettingRow label="Border color"><OptionalColorControl value={appearance.surface.border_color} fallback="#1E293B" disabled={disabled} onChange={(border_color) => update('surface', { ...appearance.surface, border_color })} /></SettingRow>
        <SettingRow label="Border width"><NumberControl value={appearance.surface.border_width} min={0} max={4} suffix="px" disabled={disabled} onChange={(border_width) => update('surface', { ...appearance.surface, border_width })} /></SettingRow>
        <SettingRow label="Radius"><NumberControl value={appearance.surface.border_radius} min={0} max={32} suffix="px" disabled={disabled} onChange={(border_radius) => update('surface', { ...appearance.surface, border_radius })} /></SettingRow>
        <SettingRow label="Shadow">
          <select value={appearance.surface.shadow} disabled={disabled} onChange={(event) => update('surface', { ...appearance.surface, shadow: event.target.value as ChatSurfaceAppearance['surface']['shadow'] })} className={selectClassName}>
            <option value="none">None</option><option value="sm">Small</option><option value="md">Medium</option><option value="lg">Large</option>
          </select>
        </SettingRow>
        <SubsectionTitle title="Conversation" description="Scrollable area containing messages and execution feedback." />
        <SettingRow label="Background"><OptionalColorControl value={appearance.conversation.background_color} fallback="#020817" disabled={disabled} onChange={(background_color) => update('conversation', { ...appearance.conversation, background_color })} /></SettingRow>
        <SettingRow label="Padding"><NumberControl value={appearance.conversation.padding} min={0} max={48} suffix="px" disabled={disabled} onChange={(padding) => update('conversation', { ...appearance.conversation, padding })} /></SettingRow>
        <SettingRow label="Message gap"><NumberControl value={appearance.conversation.message_gap} min={0} max={32} suffix="px" disabled={disabled} onChange={(message_gap) => update('conversation', { ...appearance.conversation, message_gap })} /></SettingRow>
        <SettingRow label="Content width" description="Maximum width used by the conversation content inside the surface."><NumberControl value={appearance.conversation.max_content_width} min={40} max={100} suffix="%" disabled={disabled} onChange={(max_content_width) => update('conversation', { ...appearance.conversation, max_content_width })} /></SettingRow>
      </SettingPanel>
    )
  }

  if (section === 'messages') {
    const messageValue = appearance.messages[messageRole]
    const roleFallback = messageRole === 'user' ? appearance.primary_color : '#0B1220'
    return (
      <SettingPanel title="Messages" description="Edit one message role at a time without expanding three large forms." action={resetAction}>
        <div className="border-b border-border/60 py-3.5"><MessageRoleSelector value={messageRole} onChange={setMessageRole} /></div>
        <MessageRows value={messageValue} primaryColor={roleFallback} disabled={disabled} onChange={(next) => update('messages', { ...appearance.messages, [messageRole]: next })} />
      </SettingPanel>
    )
  }

  if (section === 'composer') {
    return (
      <SettingPanel title="Composer and input" description="Configure the bottom composer shell separately from the text input itself." action={resetAction}>
        <SubsectionTitle title="Composer" description="Container that holds the input and send action." />
        <SettingRow label="Background"><OptionalColorControl value={appearance.composer.background_color} fallback="#0F1729" disabled={disabled} onChange={(background_color) => update('composer', { ...appearance.composer, background_color })} /></SettingRow>
        <SettingRow label="Border color"><OptionalColorControl value={appearance.composer.border_color} fallback="#1E293B" disabled={disabled} onChange={(border_color) => update('composer', { ...appearance.composer, border_color })} /></SettingRow>
        <SettingRow label="Padding"><NumberControl value={appearance.composer.padding} min={0} max={32} suffix="px" disabled={disabled} onChange={(padding) => update('composer', { ...appearance.composer, padding })} /></SettingRow>
        <SubsectionTitle title="Input" description="Text entry control inside the composer." />
        <SettingRow label="Background"><OptionalColorControl value={appearance.input.background_color} fallback="#0B1220" disabled={disabled} onChange={(background_color) => update('input', { ...appearance.input, background_color })} /></SettingRow>
        <SettingRow label="Text color"><OptionalColorControl value={appearance.input.text_color} fallback="#F8FAFC" disabled={disabled} onChange={(text_color) => update('input', { ...appearance.input, text_color })} /></SettingRow>
        <SettingRow label="Placeholder color"><OptionalColorControl value={appearance.input.placeholder_color} fallback="#94A3B8" disabled={disabled} onChange={(placeholder_color) => update('input', { ...appearance.input, placeholder_color })} /></SettingRow>
        <SettingRow label="Border color"><OptionalColorControl value={appearance.input.border_color} fallback="#334155" disabled={disabled} onChange={(border_color) => update('input', { ...appearance.input, border_color })} /></SettingRow>
        <SettingRow label="Focus border"><OptionalColorControl value={appearance.input.focus_border_color} fallback={appearance.primary_color} disabled={disabled} onChange={(focus_border_color) => update('input', { ...appearance.input, focus_border_color })} /></SettingRow>
        <SettingRow label="Radius"><NumberControl value={appearance.input.border_radius} min={0} max={32} suffix="px" disabled={disabled} onChange={(border_radius) => update('input', { ...appearance.input, border_radius })} /></SettingRow>
        <SettingRow label="Font size"><NumberControl value={appearance.input.font_size} min={12} max={20} suffix="px" disabled={disabled} onChange={(font_size) => update('input', { ...appearance.input, font_size })} /></SettingRow>
        <SettingRow label="Vertical padding"><NumberControl value={appearance.input.padding_y} min={6} max={20} suffix="px" disabled={disabled} onChange={(padding_y) => update('input', { ...appearance.input, padding_y })} /></SettingRow>
        <SettingRow label="Horizontal padding"><NumberControl value={appearance.input.padding_x} min={8} max={28} suffix="px" disabled={disabled} onChange={(padding_x) => update('input', { ...appearance.input, padding_x })} /></SettingRow>
      </SettingPanel>
    )
  }

  if (section === 'send-button') {
    return (
      <SettingPanel title="Send button" description="Choose presentation and style for the message submission action." action={resetAction}>
        <SettingRow label="Variant" description="Display text, an icon, or both.">
          <select value={appearance.send_button.variant} disabled={disabled} onChange={(event) => update('send_button', { ...appearance.send_button, variant: event.target.value as ChatSurfaceAppearance['send_button']['variant'] })} className={selectClassName}>
            <option value="text">Text</option><option value="icon">Icon</option><option value="icon_text">Icon + text</option>
          </select>
        </SettingRow>
        <SettingRow label="Label"><Input value={appearance.send_button.label} disabled={disabled} maxLength={32} onChange={(event) => update('send_button', { ...appearance.send_button, label: event.target.value })} /></SettingRow>
        <SettingRow label="Icon">
          <select value={appearance.send_button.icon} disabled={disabled} onChange={(event) => update('send_button', { ...appearance.send_button, icon: event.target.value as ChatSurfaceAppearance['send_button']['icon'] })} className={selectClassName}>
            <option value="arrow_up">Arrow up</option><option value="arrow_right">Arrow right</option><option value="none">No icon</option>
          </select>
        </SettingRow>
        <SettingRow label="Background"><OptionalColorControl value={appearance.send_button.background_color} fallback={appearance.primary_color} disabled={disabled} onChange={(background_color) => update('send_button', { ...appearance.send_button, background_color })} /></SettingRow>
        <SettingRow label="Text color"><OptionalColorControl value={appearance.send_button.text_color} fallback="#FFFFFF" disabled={disabled} onChange={(text_color) => update('send_button', { ...appearance.send_button, text_color })} /></SettingRow>
        <SettingRow label="Border color"><OptionalColorControl value={appearance.send_button.border_color} fallback={appearance.primary_color} disabled={disabled} onChange={(border_color) => update('send_button', { ...appearance.send_button, border_color })} /></SettingRow>
        <SettingRow label="Border width"><NumberControl value={appearance.send_button.border_width} min={0} max={4} suffix="px" disabled={disabled} onChange={(border_width) => update('send_button', { ...appearance.send_button, border_width })} /></SettingRow>
        <SettingRow label="Radius"><NumberControl value={appearance.send_button.border_radius} min={0} max={32} suffix="px" disabled={disabled} onChange={(border_radius) => update('send_button', { ...appearance.send_button, border_radius })} /></SettingRow>
      </SettingPanel>
    )
  }

  return (
    <SettingPanel title="Activity and response" description="Control public waiting feedback and assistant response rendering. Runtime reasoning and trace internals remain private." action={resetAction}>
      <SettingRow label="Response rendering" description="Rich mode renders the supported safe formatting subset; plain mode renders literal text.">
        <select value={appearance.response.render_mode} disabled={disabled} onChange={(event) => update('response', { render_mode: event.target.value as ChatSurfaceAppearance['response']['render_mode'] })} className={selectClassName}>
          <option value="rich">Rich</option><option value="plain">Plain text</option>
        </select>
      </SettingRow>
      <SettingRow label="Waiting state" description="Use simple typing dots or normalized execution status labels.">
        <select value={appearance.activity.mode} disabled={disabled} onChange={(event) => update('activity', { ...appearance.activity, mode: event.target.value as ChatSurfaceAppearance['activity']['mode'] })} className={selectClassName}>
          <option value="dots">Typing dots</option><option value="status">Execution status</option>
        </select>
      </SettingRow>
      <SettingRow label="Activity detail" description="Named detail remains opt-in and only uses explicitly public labels.">
        <select value={appearance.activity.detail_level} disabled={disabled || appearance.activity.mode !== 'status'} onChange={(event) => update('activity', { ...appearance.activity, detail_level: event.target.value as ChatSurfaceAppearance['activity']['detail_level'] })} className={selectClassName}>
          <option value="generic">Generic</option><option value="named">Named when explicitly configured</option>
        </select>
      </SettingRow>
      <SettingRow label="Activity indicator"><ToggleControl checked={appearance.activity.show_icon} label="Show activity spinner" disabled={disabled || appearance.activity.mode !== 'status'} onChange={(show_icon) => update('activity', { ...appearance.activity, show_icon })} /></SettingRow>
      {appearance.activity.mode === 'status' ? (
        <>
          <SubsectionTitle title="Public status labels" description="Only normalized public execution states are exposed to the ChatSurface." />
          {(Object.keys(appearance.activity.labels) as Array<keyof typeof appearance.activity.labels>).map((key) => (
            <SettingRow key={key} label={key.replaceAll('_', ' ')}>
              <Input value={appearance.activity.labels[key]} disabled={disabled} maxLength={80} onChange={(event) => update('activity', { ...appearance.activity, labels: { ...appearance.activity.labels, [key]: event.target.value } })} />
            </SettingRow>
          ))}
        </>
      ) : null}
    </SettingPanel>
  )
}
