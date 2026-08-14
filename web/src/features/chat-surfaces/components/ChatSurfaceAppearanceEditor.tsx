import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import type {
  ChatSurfaceAppearance,
  ChatSurfaceMessageStyle,
} from '@/features/chat-surfaces/types'

interface ChatSurfaceAppearanceEditorProps {
  appearance: ChatSurfaceAppearance
  disabled?: boolean
  onChange: (appearance: ChatSurfaceAppearance) => void
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">
      {children}
    </span>
  )
}

function Section({
  title,
  description,
  children,
  open = false,
}: {
  title: string
  description: string
  children: React.ReactNode
  open?: boolean
}) {
  return (
    <details open={open} className="group rounded-xl border border-border/80 bg-surface/65">
      <summary className="cursor-pointer list-none px-5 py-4 marker:hidden">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-white">{title}</h3>
            <p className="mt-1 text-xs leading-5 text-muted">{description}</p>
          </div>
          <span className="text-xs text-muted transition-transform group-open:rotate-180">⌄</span>
        </div>
      </summary>
      <div className="border-t border-border/70 px-5 py-5">{children}</div>
    </details>
  )
}

function OptionalColorField({
  label,
  value,
  fallback,
  disabled,
  onChange,
}: {
  label: string
  value: string | null
  fallback: string
  disabled?: boolean
  onChange: (value: string | null) => void
}) {
  const enabled = value !== null
  return (
    <div>
      <FieldLabel>{label}</FieldLabel>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={value ?? fallback}
          disabled={disabled || !enabled}
          onChange={(event) => onChange(event.target.value.toUpperCase())}
          className="h-10 w-14 rounded-lg border border-border bg-background p-1 disabled:opacity-45"
        />
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={disabled}
          onClick={() => onChange(enabled ? null : fallback.toUpperCase())}
        >
          {enabled ? 'Use theme' : 'Customize'}
        </Button>
        <code className="text-[11px] text-muted">{value ?? 'Theme default'}</code>
      </div>
    </div>
  )
}

function NumberField({
  label,
  value,
  min,
  max,
  suffix,
  disabled,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  suffix?: string
  disabled?: boolean
  onChange: (value: number) => void
}) {
  return (
    <label className="block">
      <FieldLabel>{label}</FieldLabel>
      <div className="flex items-center gap-2">
        <Input
          type="number"
          min={min}
          max={max}
          value={value}
          disabled={disabled}
          onChange={(event) => {
            const next = Number(event.target.value)
            if (Number.isFinite(next)) onChange(next)
          }}
        />
        {suffix ? <span className="shrink-0 text-xs text-muted">{suffix}</span> : null}
      </div>
    </label>
  )
}

function MessageStyleEditor({
  title,
  value,
  primaryColor,
  disabled,
  onChange,
}: {
  title: string
  value: ChatSurfaceMessageStyle
  primaryColor: string
  disabled?: boolean
  onChange: (value: ChatSurfaceMessageStyle) => void
}) {
  return (
    <div className="rounded-xl border border-border/70 bg-background/45 p-4">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-white/80">{title}</h4>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <OptionalColorField
          label="Background"
          value={value.background_color}
          fallback={primaryColor}
          disabled={disabled}
          onChange={(background_color) => onChange({ ...value, background_color })}
        />
        <OptionalColorField
          label="Text"
          value={value.text_color}
          fallback="#FFFFFF"
          disabled={disabled}
          onChange={(text_color) => onChange({ ...value, text_color })}
        />
        <OptionalColorField
          label="Border"
          value={value.border_color}
          fallback="#CBD1DC"
          disabled={disabled}
          onChange={(border_color) => onChange({ ...value, border_color })}
        />
        <NumberField
          label="Border width"
          value={value.border_width}
          min={0}
          max={4}
          suffix="px"
          disabled={disabled}
          onChange={(border_width) => onChange({ ...value, border_width })}
        />
        <NumberField
          label="Radius"
          value={value.border_radius}
          min={0}
          max={32}
          suffix="px"
          disabled={disabled}
          onChange={(border_radius) => onChange({ ...value, border_radius })}
        />
        <NumberField
          label="Maximum width"
          value={value.max_width}
          min={40}
          max={100}
          suffix="%"
          disabled={disabled}
          onChange={(max_width) => onChange({ ...value, max_width })}
        />
        <NumberField
          label="Vertical padding"
          value={value.padding_y}
          min={4}
          max={24}
          suffix="px"
          disabled={disabled}
          onChange={(padding_y) => onChange({ ...value, padding_y })}
        />
        <NumberField
          label="Horizontal padding"
          value={value.padding_x}
          min={6}
          max={32}
          suffix="px"
          disabled={disabled}
          onChange={(padding_x) => onChange({ ...value, padding_x })}
        />
      </div>
      <label className="mt-4 flex items-center gap-2 text-xs text-muted">
        <input
          type="checkbox"
          checked={value.show_avatar}
          disabled={disabled}
          onChange={(event) => onChange({ ...value, show_avatar: event.target.checked })}
        />
        Show role avatar
      </label>
    </div>
  )
}

export function ChatSurfaceAppearanceEditor({
  appearance,
  disabled,
  onChange,
}: ChatSurfaceAppearanceEditorProps) {
  const update = <K extends keyof ChatSurfaceAppearance>(
    key: K,
    value: ChatSurfaceAppearance[K],
  ) => onChange({ ...appearance, [key]: value })

  return (
    <div className="space-y-4">
      <Section
        title="General"
        description="Identity, base theme and the initial conversation copy."
        open
      >
        <div className="space-y-4">
          <label className="block">
            <FieldLabel>Display title</FieldLabel>
            <Input
              value={appearance.title}
              disabled={disabled}
              maxLength={80}
              onChange={(event) => update('title', event.target.value)}
            />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <FieldLabel>Theme</FieldLabel>
              <select
                value={appearance.theme}
                disabled={disabled}
                onChange={(event) => update('theme', event.target.value as ChatSurfaceAppearance['theme'])}
                className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm disabled:opacity-60"
              >
                <option value="system">System</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </label>
            <div>
              <FieldLabel>Primary color</FieldLabel>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={appearance.primary_color}
                  disabled={disabled}
                  onChange={(event) => update('primary_color', event.target.value.toUpperCase())}
                  className="h-10 w-14 rounded-lg border border-border bg-background p-1 disabled:opacity-60"
                />
                <code className="text-xs text-muted">{appearance.primary_color}</code>
              </div>
            </div>
          </div>
          <label className="block">
            <FieldLabel>Placeholder</FieldLabel>
            <Input
              value={appearance.placeholder}
              disabled={disabled}
              maxLength={120}
              onChange={(event) => update('placeholder', event.target.value)}
            />
          </label>
          <label className="block">
            <FieldLabel>Welcome message</FieldLabel>
            <Textarea
              value={appearance.welcome_message ?? ''}
              disabled={disabled}
              rows={3}
              maxLength={500}
              onChange={(event) => update('welcome_message', event.target.value)}
            />
          </label>
        </div>
      </Section>

      <Section title="Header" description="Control the top bar independently from the rest of the chat.">
        <label className="mb-4 flex items-center gap-2 text-sm text-white">
          <input
            type="checkbox"
            checked={appearance.header.visible}
            disabled={disabled}
            onChange={(event) => update('header', { ...appearance.header, visible: event.target.checked })}
          />
          Show header
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <OptionalColorField
            label="Background"
            value={appearance.header.background_color}
            fallback={appearance.primary_color}
            disabled={disabled}
            onChange={(background_color) => update('header', { ...appearance.header, background_color })}
          />
          <OptionalColorField
            label="Text"
            value={appearance.header.text_color}
            fallback="#FFFFFF"
            disabled={disabled}
            onChange={(text_color) => update('header', { ...appearance.header, text_color })}
          />
          <OptionalColorField
            label="Border"
            value={appearance.header.border_color}
            fallback="#CBD1DC"
            disabled={disabled}
            onChange={(border_color) => update('header', { ...appearance.header, border_color })}
          />
          <NumberField
            label="Border width"
            value={appearance.header.border_width}
            min={0}
            max={4}
            suffix="px"
            disabled={disabled}
            onChange={(border_width) => update('header', { ...appearance.header, border_width })}
          />
          <NumberField
            label="Height"
            value={appearance.header.height}
            min={40}
            max={96}
            suffix="px"
            disabled={disabled}
            onChange={(height) => update('header', { ...appearance.header, height })}
          />
          <NumberField
            label="Horizontal padding"
            value={appearance.header.padding}
            min={0}
            max={40}
            suffix="px"
            disabled={disabled}
            onChange={(padding) => update('header', { ...appearance.header, padding })}
          />
          <label className="block">
            <FieldLabel>Alignment</FieldLabel>
            <select
              value={appearance.header.alignment}
              disabled={disabled}
              onChange={(event) => update('header', {
                ...appearance.header,
                alignment: event.target.value as ChatSurfaceAppearance['header']['alignment'],
              })}
              className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm disabled:opacity-60"
            >
              <option value="left">Left</option>
              <option value="center">Center</option>
              <option value="right">Right</option>
            </select>
          </label>
        </div>
      </Section>

      <Section title="Chat surface" description="Outer surface and the scrolling conversation area.">
        <div className="grid gap-4 sm:grid-cols-2">
          <OptionalColorField
            label="Surface background"
            value={appearance.surface.background_color}
            fallback="#F7F8FB"
            disabled={disabled}
            onChange={(background_color) => update('surface', { ...appearance.surface, background_color })}
          />
          <OptionalColorField
            label="Surface border"
            value={appearance.surface.border_color}
            fallback="#E2E5EC"
            disabled={disabled}
            onChange={(border_color) => update('surface', { ...appearance.surface, border_color })}
          />
          <NumberField
            label="Surface border width"
            value={appearance.surface.border_width}
            min={0}
            max={4}
            suffix="px"
            disabled={disabled}
            onChange={(border_width) => update('surface', { ...appearance.surface, border_width })}
          />
          <NumberField
            label="Surface radius"
            value={appearance.surface.border_radius}
            min={0}
            max={32}
            suffix="px"
            disabled={disabled}
            onChange={(border_radius) => update('surface', { ...appearance.surface, border_radius })}
          />
          <label className="block">
            <FieldLabel>Shadow</FieldLabel>
            <select
              value={appearance.surface.shadow}
              disabled={disabled}
              onChange={(event) => update('surface', {
                ...appearance.surface,
                shadow: event.target.value as ChatSurfaceAppearance['surface']['shadow'],
              })}
              className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm disabled:opacity-60"
            >
              <option value="none">None</option>
              <option value="sm">Small</option>
              <option value="md">Medium</option>
              <option value="lg">Large</option>
            </select>
          </label>
          <OptionalColorField
            label="Conversation background"
            value={appearance.conversation.background_color}
            fallback="#F7F8FB"
            disabled={disabled}
            onChange={(background_color) => update('conversation', { ...appearance.conversation, background_color })}
          />
          <NumberField
            label="Conversation padding"
            value={appearance.conversation.padding}
            min={0}
            max={48}
            suffix="px"
            disabled={disabled}
            onChange={(padding) => update('conversation', { ...appearance.conversation, padding })}
          />
          <NumberField
            label="Message gap"
            value={appearance.conversation.message_gap}
            min={0}
            max={32}
            suffix="px"
            disabled={disabled}
            onChange={(message_gap) => update('conversation', { ...appearance.conversation, message_gap })}
          />
          <NumberField
            label="Content width"
            value={appearance.conversation.max_content_width}
            min={40}
            max={100}
            suffix="%"
            disabled={disabled}
            onChange={(max_content_width) => update('conversation', { ...appearance.conversation, max_content_width })}
          />
        </div>
      </Section>

      <Section title="Messages" description="Style user, assistant and system messages separately.">
        <div className="space-y-4">
          <MessageStyleEditor
            title="User"
            value={appearance.messages.user}
            primaryColor={appearance.primary_color}
            disabled={disabled}
            onChange={(user) => update('messages', { ...appearance.messages, user })}
          />
          <MessageStyleEditor
            title="Assistant"
            value={appearance.messages.assistant}
            primaryColor="#FFFFFF"
            disabled={disabled}
            onChange={(assistant) => update('messages', { ...appearance.messages, assistant })}
          />
          <MessageStyleEditor
            title="System"
            value={appearance.messages.system}
            primaryColor="#FFFFFF"
            disabled={disabled}
            onChange={(system) => update('messages', { ...appearance.messages, system })}
          />
        </div>
      </Section>

      <Section title="Composer and input" description="Customize the bottom composer and text input independently.">
        <div className="grid gap-4 sm:grid-cols-2">
          <OptionalColorField
            label="Composer background"
            value={appearance.composer.background_color}
            fallback="#FFFFFF"
            disabled={disabled}
            onChange={(background_color) => update('composer', { ...appearance.composer, background_color })}
          />
          <OptionalColorField
            label="Composer border"
            value={appearance.composer.border_color}
            fallback="#E2E5EC"
            disabled={disabled}
            onChange={(border_color) => update('composer', { ...appearance.composer, border_color })}
          />
          <NumberField
            label="Composer padding"
            value={appearance.composer.padding}
            min={0}
            max={32}
            suffix="px"
            disabled={disabled}
            onChange={(padding) => update('composer', { ...appearance.composer, padding })}
          />
          <OptionalColorField
            label="Input background"
            value={appearance.input.background_color}
            fallback="#FFFFFF"
            disabled={disabled}
            onChange={(background_color) => update('input', { ...appearance.input, background_color })}
          />
          <OptionalColorField
            label="Input text"
            value={appearance.input.text_color}
            fallback="#172033"
            disabled={disabled}
            onChange={(text_color) => update('input', { ...appearance.input, text_color })}
          />
          <OptionalColorField
            label="Placeholder"
            value={appearance.input.placeholder_color}
            fallback="#667085"
            disabled={disabled}
            onChange={(placeholder_color) => update('input', { ...appearance.input, placeholder_color })}
          />
          <OptionalColorField
            label="Input border"
            value={appearance.input.border_color}
            fallback="#CBD1DC"
            disabled={disabled}
            onChange={(border_color) => update('input', { ...appearance.input, border_color })}
          />
          <OptionalColorField
            label="Focus border"
            value={appearance.input.focus_border_color}
            fallback={appearance.primary_color}
            disabled={disabled}
            onChange={(focus_border_color) => update('input', { ...appearance.input, focus_border_color })}
          />
          <NumberField
            label="Input radius"
            value={appearance.input.border_radius}
            min={0}
            max={32}
            suffix="px"
            disabled={disabled}
            onChange={(border_radius) => update('input', { ...appearance.input, border_radius })}
          />
          <NumberField
            label="Font size"
            value={appearance.input.font_size}
            min={12}
            max={20}
            suffix="px"
            disabled={disabled}
            onChange={(font_size) => update('input', { ...appearance.input, font_size })}
          />
          <NumberField
            label="Vertical padding"
            value={appearance.input.padding_y}
            min={6}
            max={20}
            suffix="px"
            disabled={disabled}
            onChange={(padding_y) => update('input', { ...appearance.input, padding_y })}
          />
          <NumberField
            label="Horizontal padding"
            value={appearance.input.padding_x}
            min={8}
            max={28}
            suffix="px"
            disabled={disabled}
            onChange={(padding_x) => update('input', { ...appearance.input, padding_x })}
          />
        </div>
      </Section>

      <Section title="Send button" description="Choose label/icon presentation and style the send action separately.">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <FieldLabel>Variant</FieldLabel>
            <select
              value={appearance.send_button.variant}
              disabled={disabled}
              onChange={(event) => update('send_button', {
                ...appearance.send_button,
                variant: event.target.value as ChatSurfaceAppearance['send_button']['variant'],
              })}
              className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm disabled:opacity-60"
            >
              <option value="text">Text</option>
              <option value="icon">Icon</option>
              <option value="icon_text">Icon + text</option>
            </select>
          </label>
          <label className="block">
            <FieldLabel>Label</FieldLabel>
            <Input
              value={appearance.send_button.label}
              disabled={disabled}
              maxLength={32}
              onChange={(event) => update('send_button', { ...appearance.send_button, label: event.target.value })}
            />
          </label>
          <label className="block">
            <FieldLabel>Icon</FieldLabel>
            <select
              value={appearance.send_button.icon}
              disabled={disabled}
              onChange={(event) => update('send_button', {
                ...appearance.send_button,
                icon: event.target.value as ChatSurfaceAppearance['send_button']['icon'],
              })}
              className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm disabled:opacity-60"
            >
              <option value="arrow_up">Arrow up</option>
              <option value="arrow_right">Arrow right</option>
              <option value="none">No icon</option>
            </select>
          </label>
          <OptionalColorField
            label="Background"
            value={appearance.send_button.background_color}
            fallback={appearance.primary_color}
            disabled={disabled}
            onChange={(background_color) => update('send_button', { ...appearance.send_button, background_color })}
          />
          <OptionalColorField
            label="Text"
            value={appearance.send_button.text_color}
            fallback="#FFFFFF"
            disabled={disabled}
            onChange={(text_color) => update('send_button', { ...appearance.send_button, text_color })}
          />
          <OptionalColorField
            label="Border"
            value={appearance.send_button.border_color}
            fallback={appearance.primary_color}
            disabled={disabled}
            onChange={(border_color) => update('send_button', { ...appearance.send_button, border_color })}
          />
          <NumberField
            label="Border width"
            value={appearance.send_button.border_width}
            min={0}
            max={4}
            suffix="px"
            disabled={disabled}
            onChange={(border_width) => update('send_button', { ...appearance.send_button, border_width })}
          />
          <NumberField
            label="Radius"
            value={appearance.send_button.border_radius}
            min={0}
            max={32}
            suffix="px"
            disabled={disabled}
            onChange={(border_radius) => update('send_button', { ...appearance.send_button, border_radius })}
          />
        </div>
      </Section>

      <Section title="Activity and response" description="Control waiting feedback and how assistant responses are rendered.">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <FieldLabel>Waiting state</FieldLabel>
            <select
              value={appearance.activity.mode}
              disabled={disabled}
              onChange={(event) => update('activity', {
                ...appearance.activity,
                mode: event.target.value as ChatSurfaceAppearance['activity']['mode'],
              })}
              className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm disabled:opacity-60"
            >
              <option value="dots">Typing dots</option>
              <option value="status">Execution status</option>
            </select>
          </label>
          <label className="block">
            <FieldLabel>Activity detail</FieldLabel>
            <select
              value={appearance.activity.detail_level}
              disabled={disabled || appearance.activity.mode !== 'status'}
              onChange={(event) => update('activity', {
                ...appearance.activity,
                detail_level: event.target.value as ChatSurfaceAppearance['activity']['detail_level'],
              })}
              className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm disabled:opacity-60"
            >
              <option value="generic">Generic</option>
              <option value="named">Named when explicitly configured</option>
            </select>
          </label>
          <label className="block">
            <FieldLabel>Response rendering</FieldLabel>
            <select
              value={appearance.response.render_mode}
              disabled={disabled}
              onChange={(event) => update('response', {
                render_mode: event.target.value as ChatSurfaceAppearance['response']['render_mode'],
              })}
              className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm disabled:opacity-60"
            >
              <option value="rich">Rich</option>
              <option value="plain">Plain text</option>
            </select>
          </label>
          <label className="flex items-end gap-2 pb-2 text-xs text-muted">
            <input
              type="checkbox"
              checked={appearance.activity.show_icon}
              disabled={disabled || appearance.activity.mode !== 'status'}
              onChange={(event) => update('activity', { ...appearance.activity, show_icon: event.target.checked })}
            />
            Show activity spinner
          </label>
        </div>
        {appearance.activity.mode === 'status' ? (
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            {(Object.keys(appearance.activity.labels) as Array<keyof typeof appearance.activity.labels>).map((key) => (
              <label key={key} className="block">
                <FieldLabel>{key.replaceAll('_', ' ')}</FieldLabel>
                <Input
                  value={appearance.activity.labels[key]}
                  disabled={disabled}
                  maxLength={80}
                  onChange={(event) => update('activity', {
                    ...appearance.activity,
                    labels: { ...appearance.activity.labels, [key]: event.target.value },
                  })}
                />
              </label>
            ))}
          </div>
        ) : null}
        <p className="mt-4 text-[11px] leading-5 text-muted">
          Activity displays normalized execution states only. Reasoning, prompts, tool payloads and trace internals are never rendered in ChatSurface.
        </p>
      </Section>
    </div>
  )
}
