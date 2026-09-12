import { woobeLayers } from '@woobe/ui'

export const UI_LAYER_Z_INDEX = {
  playgroundChrome: woobeLayers.playgroundChrome,
  modal: woobeLayers.modal,
  nestedModal: woobeLayers.nestedModal,
  focus: woobeLayers.focus,
} as const

export const UI_LAYER_CLASS = {
  playgroundChrome: 'z-playground-chrome',
  modal: 'z-modal',
  nestedModal: 'z-nested-modal',
  focus: 'z-focus',
} as const

export type DialogLayer = 'modal' | 'nestedModal'
