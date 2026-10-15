import { expect, test } from '@playwright/test'
import { hasRenderedFont, platformFontFamily } from '../support/font-evidence'

test('recognizes the actual Inter Fontations metadata reported by CI', () => {
  const fonts = [{ familyName: 'Inter (Fontations)', isCustomFont: true, glyphCount: 18 }]
  expect(hasRenderedFont(fonts, 'Inter', 'web')).toBe(true)
  expect(hasRenderedFont(fonts, 'JetBrains Mono', 'web')).toBe(false)
  expect(platformFontFamily(fonts[0].familyName)).toBe('Inter')
})

test('recognizes both font backends for both self-hosted families', () => {
  for (const family of ['Inter', 'JetBrains Mono']) for (const suffix of ['', ' (Fontations)']) {
    expect(hasRenderedFont([{ familyName: family + suffix, isCustomFont: true, glyphCount: 65 }], family, 'web')).toBe(true)
  }
})

test('rejects unrelated families, variants and unrecognized annotations', () => {
  for (const familyName of ['Arial', 'Inter Display (Fontations)', 'Inter (other backend)', 'Inter (Fontations) fallback']) {
    expect(hasRenderedFont([{ familyName, isCustomFont: true, glyphCount: 18 }], 'Inter', 'web')).toBe(false)
  }
})

test('requires actual glyphs and the requested webfont origin', () => {
  expect(hasRenderedFont([{ familyName: 'Inter (Fontations)', isCustomFont: true, glyphCount: 0 }], 'Inter', 'web')).toBe(false)
  expect(hasRenderedFont([{ familyName: 'Inter (Fontations)', isCustomFont: false, glyphCount: 18 }], 'Inter', 'web')).toBe(false)
  expect(hasRenderedFont([], 'Inter', 'web')).toBe(false)
})

test('keeps the Georgia system-font requirement separate from webfonts', () => {
  expect(hasRenderedFont([{ familyName: 'Georgia', isCustomFont: false, glyphCount: 16 }], 'Georgia', 'system')).toBe(true)
  expect(hasRenderedFont([{ familyName: 'Georgia', isCustomFont: true, glyphCount: 16 }], 'Georgia', 'system')).toBe(false)
  expect(hasRenderedFont([{ familyName: 'Liberation Serif', isCustomFont: false, glyphCount: 16 }], 'Georgia', 'system')).toBe(false)
})
