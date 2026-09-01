import { describe, expect, it } from 'vitest'
import { UI_LAYER_Z_INDEX } from './ui-layers'

describe('global UI layer hierarchy', () => {
  it('keeps playground chrome below modal, nested modal, and focus layers', () => {
    expect(UI_LAYER_Z_INDEX.playgroundChrome).toBeLessThan(UI_LAYER_Z_INDEX.modal)
    expect(UI_LAYER_Z_INDEX.modal).toBeLessThan(UI_LAYER_Z_INDEX.nestedModal)
    expect(UI_LAYER_Z_INDEX.nestedModal).toBeLessThan(UI_LAYER_Z_INDEX.focus)
  })
})
