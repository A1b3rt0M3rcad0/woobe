export interface PlatformFontEvidence {
  familyName: string
  isCustomFont: boolean
  glyphCount: number
}

/** Chromium's Fontations backend appends its name to the CDP family label. */
export function platformFontFamily(name: string) {
  return name.replace(/ \(Fontations\)$/, '')
}

export function hasRenderedFont(fonts: PlatformFontEvidence[], family: string, origin: 'web' | 'system') {
  return fonts.some(font => font.glyphCount > 0
    && font.isCustomFont === (origin === 'web')
    && platformFontFamily(font.familyName) === family)
}
