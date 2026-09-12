import { woobeColors } from './src/tokens/colors'
import { woobeRadius, woobeTypography } from './src/tokens'

const woobeTailwindPreset = {
  theme: {
    extend: {
      colors: woobeColors,
      fontFamily: {
        sans: [...woobeTypography.sans],
        mono: [...woobeTypography.mono],
      },
      borderRadius: {
        technical: woobeRadius.technical,
        control: woobeRadius.control,
        container: woobeRadius.container,
      },
    },
  },
}

export default woobeTailwindPreset
