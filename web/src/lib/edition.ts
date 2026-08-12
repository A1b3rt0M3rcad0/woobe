export type WoobeEdition = 'community' | 'cloud'

export const woobeEdition: WoobeEdition =
  import.meta.env.VITE_WOOBE_EDITION === 'cloud' ? 'cloud' : 'community'

export const isCloudEdition = woobeEdition === 'cloud'
