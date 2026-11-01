import { Columns2, Expand, Move, RotateCcw, Shrink, ZoomIn, ZoomOut } from 'lucide-react'
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import tokens from '../../../../design/tokens.json'
import { cn } from '../../design/components'
import { jpeg, png, type Analysis, type LesionKey } from '../api'
import { viewerGeometry } from '../viewerGeometry'

export type Layer = LesionKey | 'cam' | 'macula' | 'disc'
const KEYS: LesionKey[] = ['MA', 'HE', 'EX', 'SE']
const control = 'inline-flex min-h-[36px] items-center justify-center gap-2 rounded-control border border-border-viewer px-3 py-2 text-secondary text-neutral-200 hover:bg-surface-viewerRaised disabled:opacity-40'

export function ImageViewer({ analysis: a, eye, layers, original, onOriginal, onMode, onToggle, name }:
  { analysis: Analysis; eye: string; layers: Set<Layer>; original: boolean; onOriginal: () => void; onMode: (mode: 'lesions' | 'attribution') => void; onToggle: (layer: Layer) => void; name: (key: LesionKey) => string }) {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [compare, setCompare] = useState(false)
  const [opacity, setOpacity] = useState(.75)
  const [size, setSize] = useState({ w: a.image.width, h: a.image.height })
  const [failed, setFailed] = useState(false)
  const [full, setFull] = useState(false)
  const [screenMessage, setScreenMessage] = useState<string | null>(null)
  const viewer = useRef<HTMLElement>(null)
  useEffect(() => {
    const change = () => setFull(document.fullscreenElement === viewer.current)
    document.addEventListener('fullscreenchange', change)
    return () => document.removeEventListener('fullscreenchange', change)
  }, [])
  const descriptionId = useId()
  const mode = original ? 'original' : layers.has('cam') ? 'attribution' : 'lesions'
  const ok = a.status === 'ok' && !!a.findings
  function reset() { setZoom(1); setPan({ x: 0, y: 0 }) }
  function changeZoom(value: number) { const next = Math.min(4, Math.max(1, value)); setZoom(next); if (next === 1) setPan({ x: 0, y: 0 }) }
  async function changeFullscreen() {
    setScreenMessage(null)
    try {
      if (document.fullscreenElement === viewer.current) await document.exitFullscreen()
      else if (viewer.current?.requestFullscreen) await viewer.current.requestFullscreen()
      else setScreenMessage('Fullscreen is unavailable in this browser. Use the zoom controls to inspect the image.')
    } catch { setScreenMessage('The browser could not open fullscreen. Use the zoom controls or maximise the browser window.') }
  }
  const overlay = <>
    <div className="pointer-events-none absolute inset-0" style={{ opacity }}>
      {mode === 'lesions' && a.lesions?.filter(l => layers.has(l.key)).map(l => <img key={l.key} src={png(l.overlay)} alt="" aria-hidden draggable={false} className="absolute inset-0 h-full w-full" />)}
      {mode === 'attribution' && a.attribution && <img src={png(a.attribution.overlay)} alt="" aria-hidden draggable={false} className="absolute inset-0 h-full w-full" />}
    </div>
    {mode === 'lesions' && a.findings && <svg viewBox={`0 0 ${size.w} ${size.h}`} aria-hidden className="pointer-events-none absolute inset-0 h-full w-full">
      {layers.has('macula') && <g stroke={tokens.color.landmark.macula} fill="none">
        <circle cx={a.findings.landmarks.fovea.x} cy={a.findings.landmarks.fovea.y} r={a.findings.landmarks.disc_diameter_px} strokeWidth={2} strokeDasharray={a.findings.landmarks.fovea.uncertain ? '6 6' : undefined} />
        <circle cx={a.findings.landmarks.fovea.x} cy={a.findings.landmarks.fovea.y} r={4} fill={tokens.color.landmark.macula} />
      </g>}
      {layers.has('disc') && <circle cx={a.findings.landmarks.optic_disc.x} cy={a.findings.landmarks.optic_disc.y} r={a.findings.landmarks.optic_disc.radius_px} stroke={tokens.color.landmark.disc} strokeWidth={2} fill="none" />}
    </svg>}
  </>
  return <section ref={viewer} data-viewer aria-label="Retinal image viewer" aria-describedby={descriptionId} className="overflow-hidden rounded-card bg-surface-viewer text-neutral-200">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-viewer p-3 sm:px-4">
      <div role="group" aria-label="Image display" className="flex flex-wrap gap-1">
        {(['original', 'lesions', 'attribution'] as const).map(m => <button type="button" key={m} disabled={m !== 'original' && (!ok || (m === 'attribution' && !a.attribution))}
          aria-pressed={mode === m} onClick={() => m === 'original' ? onOriginal() : onMode(m)}
          className={cn('min-h-[40px] rounded-control px-3 py-2 text-secondary font-medium disabled:opacity-40', mode === m ? 'bg-white text-neutral-900' : 'text-neutral-300 hover:bg-surface-viewerRaised')}>
          {m === 'original' ? 'Original' : m === 'lesions' ? 'Lesions' : 'Attribution'}
        </button>)}
      </div>
      <button type="button" className={control} aria-pressed={compare} disabled={mode === 'original'} onClick={() => { setCompare(v => !v); reset() }}><Columns2 size={16} aria-hidden />Compare</button>
    </div>
    {ok && mode === 'lesions' && <div className="flex flex-wrap gap-x-4 gap-y-2 border-b border-border-viewer px-4 py-3" role="group" aria-label="Predicted lesion layers">
      {KEYS.map(k => <button type="button" key={k} aria-pressed={layers.has(k)} onClick={() => onToggle(k)} className="flex min-h-[32px] items-center gap-2 text-caption text-neutral-200" title={name(k)}>
        <span aria-hidden className={cn('h-3 w-3 rounded-[3px] border', layers.has(k) ? 'border-transparent' : 'border-neutral-400')} style={{ background: layers.has(k) ? tokens.color.lesion[k] : 'transparent' }} />
        <span className={layers.has(k) ? 'text-white' : 'text-neutral-400'}>{k} <span className="tabular-nums">{a.findings?.lesions[k].count ?? 0}</span></span><span className="sr-only">{name(k)}</span>
      </button>)}
      <span className="hidden self-stretch border-l border-border-viewer sm:block" />
      {(['macula', 'disc'] as const).map(k => <button type="button" key={k} aria-pressed={layers.has(k)} onClick={() => onToggle(k)} className={cn('min-h-[32px] text-caption underline-offset-4', layers.has(k) ? 'text-white underline' : 'text-neutral-400')}>{k === 'macula' ? 'Macula' : 'Optic disc'}</button>)}
    </div>}
    <div className={cn('grid', compare && mode !== 'original' ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1')}>
      {compare && mode !== 'original' && <ImagePlate title="Original reference" image={a.display_image} alt={`${eye} original fundus photograph`} zoom={zoom} pan={pan} onPan={setPan} size={size} onSize={setSize} onError={() => setFailed(true)} />}
      <ImagePlate title={mode === 'original' ? 'Original photograph' : mode === 'lesions' ? 'Predicted lesion regions' : 'Grading model attribution'} image={a.display_image} alt={`${eye} fundus photograph`} zoom={zoom} pan={pan} onPan={setPan} size={size} onSize={setSize} onError={() => setFailed(true)}>
        {!original && ok && overlay}
      </ImagePlate>
    </div>
    {failed && <p role="alert" className="px-4 py-3 text-white">The retinal image could not be displayed. Reload the case before reviewing it.</p>}
    <div className="flex flex-wrap items-center gap-2 border-t border-border-viewer bg-surface-viewerRaised p-3 sm:px-4">
      <button type="button" className={control} aria-label="Zoom out" disabled={zoom <= 1} onClick={() => changeZoom(zoom - .25)}><ZoomOut size={17} /></button>
      <output aria-label="Magnification relative to fit" className="min-w-[48px] text-center text-caption tabular-nums">{zoom.toFixed(2)}×</output>
      <button type="button" className={control} aria-label="Zoom in" disabled={zoom >= 4} onClick={() => changeZoom(zoom + .25)}><ZoomIn size={17} /></button>
      <button type="button" className={control} onClick={reset}><RotateCcw size={15} aria-hidden />Fit</button>
      {mode !== 'original' && <label className="ml-auto flex flex-wrap items-center gap-2 text-caption">Overlay <input aria-label="Overlay opacity" className="h-9 w-[90px]" type="range" min="0" max="100" value={Math.round(opacity * 100)} onChange={e => setOpacity(Number(e.target.value) / 100)} /><span className="w-9 tabular-nums">{Math.round(opacity * 100)}%</span></label>}
      <button type="button" className={control} aria-label={full ? 'Exit fullscreen retinal viewer' : 'Expand retinal viewer'} onClick={() => void changeFullscreen()}>{full ? <Shrink size={16} /> : <Expand size={16} />}</button>
    </div>
    <div id={descriptionId} className="space-y-2 border-t border-border-viewer px-4 py-3 text-caption text-neutral-300">
      {screenMessage && <p role="status" className="text-white">{screenMessage}</p>}
      <p>{mode === 'attribution' ? 'Grad-CAM highlights regions influencing the grading model. It is not a lesion detector or proof of disease.' : mode === 'lesions' ? 'AI-predicted regions, not confirmed lesions. Counts represent connected regions; landmark positions are estimates.' : 'Original display photograph, without AI overlays.'}</p>
      {mode === 'attribution' && a.attribution?.note && <details><summary className="cursor-pointer text-neutral-200">Attribution details</summary><p className="mt-2">{a.attribution.note}</p></details>}
      <p className="flex items-center gap-2 text-neutral-400"><Move size={13} aria-hidden />Zoom, then drag or use arrow keys on the image. Magnification uses the display image.</p>
    </div>
  </section>
}

function ImagePlate({ title, image, alt, zoom, pan, onPan, size, onSize, onError, children }:
  { title: string; image: string; alt: string; zoom: number; pan: { x: number; y: number }; onPan: (p: { x: number; y: number }) => void; size: { w: number; h: number }; onSize: (s: { w: number; h: number }) => void; onError: () => void; children?: ReactNode }) {
  const frame = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; y: number; pan: { x: number; y: number } } | null>(null)
  const [bounds, setBounds] = useState({ w: 600, h: 480 })
  useEffect(() => {
    const el = frame.current
    if (!el) return
    const observer = new ResizeObserver(([entry]) => setBounds({ w: entry.contentRect.width, h: entry.contentRect.height }))
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  const { width, height, pan: position } = viewerGeometry(size, bounds, zoom, pan)
  const clamp = (p: { x: number; y: number }) => viewerGeometry(size, bounds, zoom, p).pan
  return <figure className="min-w-0">
    <figcaption className="px-4 pt-3 text-caption text-neutral-300">{title}</figcaption>
    <div ref={frame} tabIndex={0} role="region" aria-label={`${title}. Use arrow keys to pan when zoomed.`}
      className="relative flex h-[clamp(260px,48vh,620px)] items-center justify-center overflow-hidden outline-offset-[-3px]"
      style={{ cursor: zoom > 1 ? 'grab' : 'default', touchAction: zoom > 1 ? 'none' : 'pan-y' }}
      onKeyDown={e => {
        if (e.ctrlKey || e.metaKey || e.altKey || zoom === 1) return
        const movement: Record<string, { x: number; y: number }> = { ArrowLeft: { x: 40, y: 0 }, ArrowRight: { x: -40, y: 0 }, ArrowUp: { x: 0, y: 40 }, ArrowDown: { x: 0, y: -40 } }
        if (movement[e.key]) { e.preventDefault(); onPan(clamp({ x: position.x + movement[e.key].x, y: position.y + movement[e.key].y })) }
      }}
      onPointerDown={e => { if (zoom <= 1 || e.button !== 0) return; e.currentTarget.focus({ preventScroll: true }); e.currentTarget.setPointerCapture(e.pointerId); drag.current = { x: e.clientX, y: e.clientY, pan: position } }}
      onPointerMove={e => { if (drag.current) onPan(clamp({ x: drag.current.pan.x + e.clientX - drag.current.x, y: drag.current.pan.y + e.clientY - drag.current.y })) }}
      onPointerUp={e => { drag.current = null; if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId) }}
      onPointerCancel={() => { drag.current = null }} onLostPointerCapture={() => { drag.current = null }}>
      <div className="relative shrink-0" style={{ width, height, transform: `translate(${position.x}px,${position.y}px) scale(${zoom})` }}>
        <img src={jpeg(image)} alt={alt} draggable={false} className="block h-full w-full select-none" onError={onError}
          onLoad={e => { const im = e.currentTarget; if (size.w !== im.naturalWidth || size.h !== im.naturalHeight) onSize({ w: im.naturalWidth, h: im.naturalHeight }) }} />
        {children}
      </div>
    </div>
  </figure>
}
