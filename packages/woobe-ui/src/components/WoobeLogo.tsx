import { cn } from '../lib/cn'

const mark = new URL('../../brand-kit/brand/svg/woobe-mark-orange.svg', import.meta.url).href
const lightLockup = new URL('../../brand-kit/brand/svg/woobe-lockup-primary.svg', import.meta.url).href
const darkLockup = new URL('../../brand-kit/brand/svg/woobe-lockup-orange-white.svg', import.meta.url).href

export interface WoobeLogoProps {
  variant?: 'lockup' | 'mark'
  appearance?: 'auto' | 'light' | 'dark'
  decorative?: boolean
  className?: string
}

/** Original supplied vector artwork; the outlined wordmark needs no font download. */
export function WoobeLogo({ variant = 'lockup', appearance = 'auto', decorative = false, className }: WoobeLogoProps) {
  return (
    <span
      className={cn('woobe-brand inline-flex h-8 max-w-full shrink-0 align-middle', variant === 'mark' ? 'aspect-[162/128]' : 'aspect-[471/102]', className)}
      data-brand-appearance={appearance}
      data-brand-variant={variant}
      role={decorative ? undefined : 'img'}
      aria-label={decorative ? undefined : 'Woobe'}
      aria-hidden={decorative || undefined}
      translate="no"
    >
      {variant === 'mark' ? (
        <img src={mark} alt="" className="h-full w-full object-contain" width={162} height={128} />
      ) : (
        <>
          <img src={lightLockup} alt="" className="woobe-brand-on-light h-full w-full object-contain" width={471} height={102} />
          <img src={darkLockup} alt="" className="woobe-brand-on-dark h-full w-full object-contain" width={471} height={102} />
        </>
      )}
    </span>
  )
}
