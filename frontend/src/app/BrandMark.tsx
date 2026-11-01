import { useId } from 'react'
import tokens from '../design/theme'
import { BRAND, TAGLINE } from './brand'

/** The eye mark shares the workspace palette; the inverse variant sits on navy. */
export function BrandMark({ size = 40, inverse = false }: { size?: number; inverse?: boolean }) {
  const id = useId().replace(/:/g, '')
  const c = tokens.color
  return (
    <svg width={size} height={size * 0.62} viewBox="0 0 64 40" aria-hidden className="shrink-0">
      <defs>
        <linearGradient id={`g${id}`} x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor={inverse ? '#D7E7FB' : c.gradient.from} />
          <stop offset="1" stopColor={inverse ? '#A9C6FF' : c.accent.display} />
        </linearGradient>
        <radialGradient id={`i${id}`} cx="0.45" cy="0.4" r="0.6">
          <stop offset="0" stopColor={inverse ? '#D7E7FB' : c.brand['600']} />
          <stop offset="1" stopColor={inverse ? '#A9C6FF' : c.gradient.to} />
        </radialGradient>
      </defs>
      <path d="M3 20C10 8 20 3 32 3s22 5 29 17c-7 12-17 17-29 17S10 32 3 20Z" fill="none" stroke={`url(#g${id})`} strokeWidth="4" strokeLinejoin="round" />
      <circle cx="32" cy="20" r="11" fill={`url(#i${id})`} />
      <circle cx="32" cy="20" r="4.5" fill={c.neutral['900']} />
      <circle cx="35" cy="16.5" r="2" fill="#FFFFFF" opacity="0.9" />
    </svg>
  )
}

export function BrandLockup({ compact, inverse = false }: { compact?: boolean; inverse?: boolean }) {
  return (
    <span className="brand-lockup flex min-w-0 items-center gap-3" translate="no">
      <BrandMark size={compact ? 34 : 44} inverse={inverse} />
      <span className={compact ? 'hidden min-w-0 xl:block' : 'block min-w-0'}>
        <span className={'brand-name block whitespace-nowrap font-display text-[26px] leading-[1.25] ' + (inverse ? 'text-white' : 'text-text-primary')}>{BRAND}</span>
        {!compact && <span className={'mt-1 hidden text-caption sm:block ' + (inverse ? 'text-neutral-300' : 'text-text-muted')}>{TAGLINE}</span>}
      </span>
    </span>
  )
}
