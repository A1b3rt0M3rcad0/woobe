export const UI_LAYER_Z_INDEX = {
  playgroundChrome: 200,
  modal: 300,
  nestedModal: 400,
  focus: 500,
} as const

export const UI_LAYER_CLASS = {
  playgroundChrome: 'z-[200]',
  modal: 'z-[300]',
  nestedModal: 'z-[400]',
  focus: 'z-[500]',
} as const

export type DialogLayer = 'modal' | 'nestedModal'
