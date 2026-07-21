import type { ReactNode } from 'react'

type MathMLProps = {
  children?: ReactNode
  [attribute: string]: unknown
}

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      math: MathMLProps
      mfrac: MathMLProps
      mi: MathMLProps
      mn: MathMLProps
      mo: MathMLProps
      mover: MathMLProps
      mroot: MathMLProps
      mrow: MathMLProps
      mspace: MathMLProps
      msqrt: MathMLProps
      mstyle: MathMLProps
      msub: MathMLProps
      msubsup: MathMLProps
      msup: MathMLProps
      mtable: MathMLProps
      mtd: MathMLProps
      mtext: MathMLProps
      mtr: MathMLProps
      munder: MathMLProps
    }
  }
}
