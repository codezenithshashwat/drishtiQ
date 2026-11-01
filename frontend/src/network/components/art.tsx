// Hand-drawn SVG illustrations, drawn in code so they scale crisply, load instantly and work offline. Decorative: aria-hidden.
import { useId } from 'react'

export function HeroSun() {
  const id = useId()
  const rays = Array.from({ length: 28 }, (_, i) => i * (360 / 28))
  return (
    <svg className="sun" viewBox="0 0 500 440" aria-hidden focusable="false">
      <defs>
        <radialGradient id={`${id}a`} cx="50%" cy="50%" r="50%"><stop offset="0" stopColor="#FFD9A0" /><stop offset=".6" stopColor="#F9B86A" /><stop offset="1" stopColor="#E8892B" /></radialGradient>
        <linearGradient id={`${id}b`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#E6EEFB" /><stop offset="1" stopColor="#FBF0DC" /></linearGradient>
      </defs>
      <rect x="10" y="30" width="470" height="390" rx="64" fill={`url(#${id}b)`} />
      <g transform="translate(335 175)">
        <g className="rays" stroke="#E8892B" strokeOpacity=".4" strokeWidth="5" strokeLinecap="round">
          {rays.map((a) => <line key={a} x1="0" y1="-150" x2="0" y2={a % 2 ? -176 : -190} transform={`rotate(${a})`} />)}
        </g>
        <circle r="128" fill={`url(#${id}a)`} opacity=".92" />
        <circle r="128" fill="none" stroke="#fff" strokeOpacity=".5" strokeWidth="3" />
      </g>
      <path d="M0 360 C90 320 170 350 250 330 S420 300 500 335 V440 H0Z" fill="#2F7D6B" opacity=".18" />
      <path d="M0 395 C100 365 190 392 280 372 S430 360 500 385 V440 H0Z" fill="#263F83" opacity=".12" />
    </svg>
  )
}

const BG: Record<string, [string, string]> = {
  'what-is-dr': ['#E6EEFB', '#CFDDF7'], 'why-screening': ['#E3F3EC', '#C8E7DA'], 'what-happens': ['#FFF1DC', '#FBDDB0'],
  'myths-facts': ['#F3E8FB', '#E1CDF3'], 'diabetes-and-eyes': ['#FDEAEA', '#F7C9C9'], 'next-steps': ['#E6EEFB', '#FBE3BE'],
}
export const topicBg = (slug: string) => BG[slug] ?? BG['what-is-dr']

function Eye({ x = 160, y = 100, s = 1, lid = '#263F83' }: { x?: number; y?: number; s?: number; lid?: string }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path d="M-70 0 Q0 -58 70 0 Q0 58 -70 0Z" fill="#fff" stroke={lid} strokeWidth="5" strokeLinejoin="round" />
      <circle r="27" fill="#3756A0" /><circle r="27" fill="none" stroke="#1C3068" strokeWidth="3" /><circle r="11" fill="#101A3E" /><circle cx="-8" cy="-9" r="5" fill="#fff" opacity=".85" />
    </g>
  )
}

export function TopicArt({ slug, size = 'card' }: { slug: string; size?: 'card' | 'hero' }) {
  const [a, b] = topicBg(slug)
  const id = useId()
  let scene
  switch (slug) {
    case 'why-screening': scene = (<><path d="M160 24 L224 48 V104 C224 142 196 166 160 178 C124 166 96 142 96 104 V48Z" fill="#2F7D6B" /><path d="M160 24 L224 48 V104 C224 142 196 166 160 178Z" fill="#256A5A" /><Eye y={96} s={.62} lid="#fff" /><circle cx="214" cy="150" r="26" fill="#fff" /><path d="M202 150 l9 9 17-19" fill="none" stroke="#2F7D6B" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" /></>); break
    case 'what-happens': scene = (<><rect x="62" y="64" width="104" height="76" rx="18" fill="#263F83" /><rect x="84" y="50" width="34" height="20" rx="8" fill="#1C3068" /><circle cx="114" cy="102" r="26" fill="#DDE8FF" /><circle cx="114" cy="102" r="15" fill="#3756A0" /><circle cx="108" cy="96" r="4" fill="#fff" /><path d="M170 102 H198" stroke="#E8892B" strokeWidth="5" strokeLinecap="round" strokeDasharray="2 12" /><Eye x={238} y={102} s={.6} /></>); break
    case 'myths-facts': scene = (<><path d="M70 50 h100 a18 18 0 0 1 18 18 v38 a18 18 0 0 1 -18 18 h-64 l-26 22 v-22 h-10 a18 18 0 0 1 -18 -18 v-38 a18 18 0 0 1 18 -18Z" fill="#fff" stroke="#8E5CC0" strokeWidth="4" /><path d="M100 76 l24 24 M124 76 l-24 24" stroke="#B3261E" strokeWidth="7" strokeLinecap="round" /><path d="M190 96 h60 a18 18 0 0 1 18 18 v30 a18 18 0 0 1 -18 18 h-4 v20 l-24 -20 h-32 a18 18 0 0 1 -18 -18 v-30 a18 18 0 0 1 18 -18Z" fill="#2F7D6B" /><path d="M204 132 l12 12 24 -26" fill="none" stroke="#fff" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" /></>); break
    case 'diabetes-and-eyes': scene = (<><path d="M110 150 C60 118 70 70 110 70 C128 70 140 82 148 94 C156 82 168 70 186 70 C226 70 236 118 186 150 L148 178Z" fill="#E5484D" opacity=".9" transform="translate(-6 -22)" /><path d="M244 56 C226 90 214 104 214 124 a30 30 0 0 0 60 0 C274 104 262 90 244 56Z" fill="#3756A0" /><circle cx="236" cy="126" r="7" fill="#fff" opacity=".7" /><Eye x={140} y={112} s={.5} /></>); break
    case 'next-steps': scene = (<><path d="M54 160 C110 150 120 110 168 112 S250 96 270 52" fill="none" stroke="#263F83" strokeWidth="6" strokeLinecap="round" strokeDasharray="2 14" /><circle cx="54" cy="160" r="11" fill="#263F83" /><path d="M270 20 a24 24 0 0 1 24 24 c0 22 -24 40 -24 40 s-24 -18 -24 -40 a24 24 0 0 1 24 -24Z" fill="#E8892B" /><circle cx="270" cy="44" r="9" fill="#fff" /><Eye x={150} y={70} s={.5} /></>); break
    default: scene = (<><Eye y={100} s={1.25} /><g stroke="#C63D3D" strokeWidth="3" strokeLinecap="round" fill="none" opacity=".75"><path d="M146 100 q8 -8 14 -2 M174 100 q-8 8 -14 2 M160 82 v-12 M160 118 v12" /></g></>)
  }
  return (
    <svg viewBox="0 0 320 200" width="100%" height="100%" aria-hidden focusable="false" style={size === 'hero' ? { maxHeight: 240 } : undefined}>
      <defs><linearGradient id={id} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor={a} /><stop offset="1" stopColor={b} /></linearGradient></defs>
      <rect width="320" height="200" fill={`url(#${id})`} />
      <circle cx="40" cy="170" r="70" fill="#fff" opacity=".35" /><circle cx="296" cy="20" r="54" fill="#fff" opacity=".3" />
      {scene}
    </svg>
  )
}
