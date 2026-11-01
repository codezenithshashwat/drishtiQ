import { AudioLines, LoaderCircle, Mic, Volume2 } from 'lucide-react'
import type { CSSProperties } from 'react'
import type { Status } from '../saathi/SaathiProvider'

/** The signature element. Purely presentational: state and level come from the voice state machine. Every state is also
 * spelled out in text next to it, and all motion switches off under prefers-reduced-motion (see network.css). */
export function SaathiOrb({ state, level = 0, size = 200, label, onClick, as = 'button' }: { state: Status; level?: number; size?: number; label?: string; onClick?: () => void; as?: 'button' | 'div' }) {
  const Icon = state === 'listening' ? AudioLines : state === 'thinking' ? LoaderCircle : state === 'speaking' ? Volume2 : Mic
  const style = { '--orb': `${size}px`, '--level': level } as CSSProperties
  const inner = (
    <>
      <span className="glow" /><span className="ring" /><span className="ring b" />
      <span className="core"><span className="sheen" /></span>
      <Icon className={state === 'thinking' ? 'ico nw-spin' : 'ico'} size={Math.round(size * 0.26)} aria-hidden />
    </>
  )
  if (as === 'div') return <div className="nw-orb" data-state={state} style={style} aria-hidden>{inner}</div>
  return <button type="button" className="nw-orb nw-orb-btn" data-state={state} style={style} onClick={onClick} aria-label={label}>{inner}</button>
}

export function Wave({ on }: { on: boolean }) {
  return <span className="nw-wave" data-on={on} aria-hidden><i /><i /><i /><i /><i /></span>
}
