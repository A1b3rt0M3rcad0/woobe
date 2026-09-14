// @vitest-environment jsdom
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Button, Field, FieldDescription, FieldLabel, ReadOnlyField, SectionBlock, SegmentedControl, TechnicalListItem } from '@woobe/ui'
import woobeTailwindPreset from '../../../woobe-ui/tailwind.preset'
import { cn as uiCn } from '../../../woobe-ui/src/lib/cn'
import { cn } from './utils'

const fontSizes = Object.keys(woobeTailwindPreset.theme.extend.fontSize)

describe.each([['woobe-ui', uiCn], ['frontend compatibility helper', cn]] as const)('%s typography merge', (_, merge) => {
  it.each(fontSizes)('preserves text-%s alongside a foreground color in either order', (size) => {
    const font = `text-${size}`
    for (const color of ['text-accent-foreground', 'text-muted-foreground/85', 'text-primary-light', 'text-error']) {
      expect(merge(font, color).split(' ')).toEqual([font, color])
      expect(merge(color, font).split(' ')).toEqual([color, font])
    }
  })

  it('resolves size overrides independently from color overrides', () => {
    expect(merge('text-system-meta text-primary-light', 'text-product-small text-error'))
      .toBe('text-product-small text-error')
    expect(merge('text-system-meta text-muted', 'text-sm')).toBe('text-muted text-sm')
    expect(merge('text-sm text-muted', 'text-system-meta')).toBe('text-muted text-system-meta')
  })

  it('keeps responsive, descendant and important typography separate from colors', () => {
    expect(merge('sm:text-system-meta sm:text-primary-light', 'sm:text-product-small'))
      .toBe('sm:text-primary-light sm:text-product-small')
    expect(merge('[&_span]:text-system-meta [&_span]:text-muted')).toContain('[&_span]:text-system-meta')
    expect(merge('!text-system-control !text-muted')).toContain('!text-system-control')
    expect(merge('text-system-control/6 text-muted')).toContain('text-system-control/6')
  })
})

describe('configuration component typography after class merging', () => {
  it('retains the hierarchy in the rendered segmented choices, provider/model rows and supporting fields', () => {
    const root = document.createElement('div')
    root.innerHTML = renderToStaticMarkup(
      <>
        <SegmentedControl ariaLabel="Model source" items={[{ value: 'existing', label: 'Existing models' }, { value: 'manual', label: 'Manual model' }]} value="existing" onValueChange={() => undefined} />
        <TechnicalListItem density="technical" selected label="api.deepseek.com" description="OpenAI Compatible" descriptionVariant="technical" />
        <TechnicalListItem density="technical" presentation="row" label="Generation model" description="Provider model ID" descriptionVariant="technical" />
        <SectionBlock title="Provider" hierarchy="secondary" description="Select the Project connection." />
        <Field density="technical"><FieldLabel>Name</FieldLabel><FieldDescription>Initial Draft objective.</FieldDescription></Field>
        <ReadOnlyField label="Agent" value="Support Agent" />
        <Button size="sm" variant="outline">Add connection</Button>
      </>,
    )
    const textElement = (text: string) => Array.from(root.querySelectorAll('*')).find((element) => element.childElementCount === 0 && element.textContent === text)!
    for (const text of ['Existing models', 'Manual model']) {
      const button = textElement(text).closest('button')!
      expect(button.classList.contains('text-chrome-label')).toBe(true)
      expect(Array.from(button.classList).some((value) => value === 'text-accent-foreground' || value === 'text-muted-foreground')).toBe(true)
    }
    for (const text of ['api.deepseek.com', 'Generation model', 'Provider']) {
      expect(textElement(text).classList.contains('text-system-control')).toBe(true)
    }
    for (const text of ['OpenAI Compatible', 'Provider model ID', 'Select the Project connection.']) {
      expect(textElement(text).classList.contains('text-system-meta')).toBe(true)
    }
    expect(textElement('Name').classList.contains('text-product-caption')).toBe(true)
    expect(textElement('Initial Draft objective.').classList.contains('text-product-caption')).toBe(true)
    expect(textElement('Support Agent').classList.contains('text-product-small')).toBe(true)
    expect(textElement('Add connection').classList.contains('text-accent-foreground/85')).toBe(true)
  })

  it('preserves the existing clsx input support in the frontend helper', () => {
    expect(cn(['text-system-meta', { 'text-error': true, hidden: false }], null))
      .toBe('text-system-meta text-error')
  })
})
