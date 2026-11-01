// Browser speech (no SDK, no key, no cost). Recognition is Chrome/Edge (and partly Safari); synthesis is widely available
// but the set of Hindi voices depends on the device, so callers must feature-detect and always offer typing.
import type { Lang } from '../api'

type Alt = { transcript: string; confidence: number }
type Res = { isFinal: boolean; 0: Alt }
export type SRClass = new () => {
  lang: string; interimResults: boolean; continuous: boolean; maxAlternatives: number
  onresult: ((e: { resultIndex: number; results: ArrayLike<Res> }) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
  onsoundstart: (() => void) | null
  onspeechend: (() => void) | null
  start(): void; stop(): void; abort(): void
}

export function recognitionCtor(): SRClass | null {
  const w = window as unknown as { SpeechRecognition?: SRClass; webkitSpeechRecognition?: SRClass }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}
export const sttSupported = () => recognitionCtor() !== null
export const ttsSupported = () => typeof window !== 'undefined' && 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined'
export const locale = (l: Lang) => (l === 'hi' ? 'hi-IN' : 'en-IN')

export type Heard = { text: string; confidence: number }
export type RecHandlers = {
  onInterim: (t: string) => void
  onFinal: (h: Heard) => void
  onError: (code: string) => void
  onSound: (on: boolean) => void
  onEnd: (gotSpeech: boolean) => void
}

export function startRecognition(lang: Lang, h: RecHandlers) {
  const C = recognitionCtor()
  if (!C) { h.onError('unsupported'); return { stop() {}, abort() {} } }
  const r = new C()
  r.lang = locale(lang); r.interimResults = true; r.continuous = false; r.maxAlternatives = 1
  let got = false
  let done = false
  const hard = window.setTimeout(() => { try { r.stop() } catch { /* already stopped */ } }, 15000)  // never listen forever
  r.onsoundstart = () => h.onSound(true)
  r.onspeechend = () => h.onSound(false)
  r.onresult = (e) => {
    let interim = ''
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const res = e.results[i]
      if (res.isFinal) { got = true; done = true; h.onFinal({ text: res[0].transcript.trim(), confidence: res[0].confidence }) }
      else interim += res[0].transcript
    }
    if (interim) h.onInterim(interim)
  }
  r.onerror = (e) => { if (e.error !== 'aborted') h.onError(e.error) }
  r.onend = () => { window.clearTimeout(hard); h.onEnd(got || done) }
  try { r.start() } catch { h.onError('start_failed') }
  return { stop: () => { try { r.stop() } catch { /* ignore */ } }, abort: () => { window.clearTimeout(hard); try { r.abort() } catch { /* ignore */ } } }
}

let voicesCache: SpeechSynthesisVoice[] = []
function voices() {
  if (!ttsSupported()) return []
  const v = window.speechSynthesis.getVoices()
  if (v.length) voicesCache = v
  return voicesCache
}
export function pickVoice(lang: Lang): SpeechSynthesisVoice | null {
  const all = voices()
  const want = locale(lang).toLowerCase()
  const exact = all.filter((v) => v.lang.toLowerCase().replace('_', '-') === want)
  const loose = all.filter((v) => v.lang.toLowerCase().startsWith(lang))
  const pool = exact.length ? exact : loose
  // prefer a natural (network/"Google"/"Microsoft ... Online") voice when the device has one
  return pool.find((v) => /natural|online|google/i.test(v.name)) ?? pool.find((v) => !v.localService) ?? pool[0] ?? null
}
export function hasVoice(lang: Lang): boolean { return pickVoice(lang) !== null }
export function onVoicesReady(cb: () => void) {
  if (!ttsSupported()) return () => {}
  window.speechSynthesis.addEventListener('voiceschanged', cb)
  return () => window.speechSynthesis.removeEventListener('voiceschanged', cb)
}

function chunks(text: string): string[] {
  const out: string[] = []
  for (const s of text.split(/(?<=[।.!?])\s+/)) {
    let rest = s.trim()
    while (rest.length > 180) { const cut = rest.lastIndexOf(' ', 180); const at = cut > 60 ? cut : 180; out.push(rest.slice(0, at)); rest = rest.slice(at).trim() }
    if (rest) out.push(rest)
  }
  return out
}

/** Speak text in sentence-sized pieces (long utterances are cut off by some browsers). Returns a canceller. */
export function speak(text: string, lang: Lang, cb: { onStart?: () => void; onBoundary?: () => void; onEnd?: () => void }) {
  if (!ttsSupported()) { cb.onEnd?.(); return () => {} }
  const synth = window.speechSynthesis
  synth.cancel()
  const parts = chunks(text)
  let cancelled = false
  const voice = pickVoice(lang)
  parts.forEach((p, i) => {
    const u = new SpeechSynthesisUtterance(p)
    u.lang = voice?.lang ?? locale(lang)
    if (voice) u.voice = voice
    u.rate = lang === 'hi' ? 0.92 : 0.96
    if (i === 0) u.onstart = () => { if (!cancelled) cb.onStart?.() }
    u.onboundary = () => { if (!cancelled) cb.onBoundary?.() }
    if (i === parts.length - 1) { u.onend = () => { if (!cancelled) cb.onEnd?.() }; u.onerror = () => { if (!cancelled) cb.onEnd?.() } }
    synth.speak(u)
  })
  if (!parts.length) cb.onEnd?.()
  return () => { cancelled = true; synth.cancel() }
}
export function cancelSpeech() { if (ttsSupported()) window.speechSynthesis.cancel() }
