import { useId } from 'react'
import tokens from '../design/theme'
import { BRAND, TAGLINE } from './brand'

/** Eye mark: almond outline in the crimson -> coral gradient, coral iris. Inline SVG, no image file. */
export function BrandMark({ size = 40 }: { size?: number }) {
  const id = useId().replace(/:/g, '')
  const c = tokens.color
  return (
    <svg width={size} height={size * 0.62} viewBox="0 0 64 40" aria-hidden className="shrink-0">
      <defs>
        <linearGradient id={`g${id}`} x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor={c.gradient.from} />
          <stop offset="1" stopColor={c.accent.display} />
        </linearGradient>
        <radialGradient id={`i${id}`} cx="0.45" cy="0.4" r="0.6">
          <stop offset="0" stopColor={c.brand['600']} />
          <stop offset="1" stopColor={c.gradient.to} />
        </radialGradient>
      </defs>
      <path d="M3 20C10 8 20 3 32 3s22 5 29 17c-7 12-17 17-29 17S10 32 3 20Z" fill="none" stroke={`url(#g${id})`} strokeWidth="4" strokeLinejoin="round" />
      <circle cx="32" cy="20" r="11" fill={`url(#i${id})`} />
      <circle cx="32" cy="20" r="4.5" fill={c.neutral['900']} />
      <circle cx="35" cy="16.5" r="2" fill="#FFFFFF" opacity="0.9" />
    </svg>
  )
}

export function BrandLockup({ compact }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-3">
      <BrandMark size={compact ? 34 : 44} />
      <span className={compact ? 'hidden xl:block' : 'block'}>
        <span className="brand-name block font-display text-[26px] leading-none text-text-primary">{BRAND}</span>
        <span className="mt-1 hidden text-caption text-text-muted sm:block">{TAGLINE}</span>
      </span>
    </span>
  )
}
