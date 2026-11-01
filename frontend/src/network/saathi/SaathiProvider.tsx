// Saathi's brain on the client: the voice state machine (idle -> listening -> thinking -> speaking), the conversation
// transcript, and the whitelisted UI actions the server may ask for. It lives above the router so a conversation survives
// page changes (e.g. Saathi opens a camp, the person comes back and carries on).
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { navigate } from '../../app/router'
import { net, NetError, type Lang, type SaathiCard, type SaathiTurn } from '../api'
import { useI18n } from '../i18n/I18n'
import { parseNet } from '../netRouter'
import { cancelSpeech, hasVoice, onVoicesReady, speak, startRecognition, sttSupported, ttsSupported } from './speech'

export type Status = 'idle' | 'listening' | 'thinking' | 'speaking'
export type Problem = null | 'mic_denied' | 'no_mic' | 'no_speech' | 'stt_network' | 'stt_unsupported' | 'server' | 'offline' | 'low_confidence'
export type Msg = { id: number; role: 'user' | 'saathi'; text: string; lang: Lang; cards?: SaathiCard[]; links?: { label: string; to: string }[] }

type Value = {
  status: Status; level: number; msgs: Msg[]; suggestions: string[]; interim: string; problem: Problem; slow: boolean
  voiceOut: boolean; setVoiceOut: (v: boolean) => void
  supportsMic: boolean; supportsTts: boolean; noVoice: boolean
  draft: string; setDraft: (s: string) => void
  consentOpen: boolean; giveConsent: () => void; dismissConsent: () => void
  geminiOn: boolean
  send: (text: string) => Promise<void>; listen: () => void; stopListening: () => void; stopSpeaking: () => void; replay: () => void; reset: () => void
  clearProblem: () => void
}
const Ctx = createContext<Value | null>(null)
const MIC_KEY = 'dqn.mic'
const VOICE_KEY = 'dqn.voiceout'
const sget = (s: Storage, k: string) => { try { return s.getItem(k) } catch { return null } }
const sset = (s: Storage, k: string, v: string) => { try { s.setItem(k, v) } catch { /* ignore */ } }
// The conversation survives leaving the patient pages (e.g. a visit to the specialist area) for this browser tab only.
// sessionStorage is emptied when the tab closes; nothing is sent anywhere.
const CONV_KEY = 'dqn.saathi.v1'
type Saved = { msgs: Msg[]; suggestions: string[]; conv: Record<string, unknown> }
const loadSaved = (): Saved | null => {
  try {
    const v = JSON.parse(sget(sessionStorage, CONV_KEY) ?? 'null') as Saved | null
    return v && Array.isArray(v.msgs) && Array.isArray(v.suggestions) && v.conv && typeof v.conv === 'object' ? v : null
  } catch { return null }
}

export function SaathiProvider({ children }: { children: ReactNode }) {
  const { lang, setLang, t } = useI18n()
  const saved = useRef(loadSaved())
  const [status, setStatus] = useState<Status>('idle')
  const [level, setLevel] = useState(0)
  const [msgs, setMsgs] = useState<Msg[]>(() => saved.current?.msgs ?? [])
  const [suggestions, setSuggestions] = useState<string[]>(() => saved.current?.suggestions ?? [])
  const [interim, setInterim] = useState('')
  const [problem, setProblem] = useState<Problem>(null)
  const [slow, setSlow] = useState(false)
  const [voiceOut, setVoiceOutS] = useState(() => sget(localStorage, VOICE_KEY) !== '0')
  const [draft, setDraft] = useState('')
  const [consentOpen, setConsentOpen] = useState(false)
  const [voiceTick, setVoiceTick] = useState(0)
  const [geminiOn, setGeminiOn] = useState(false)
  const conv = useRef<Record<string, unknown>>(saved.current?.conv ?? {})
  const rec = useRef<{ stop(): void; abort(): void } | null>(null)
  const cancelTts = useRef<(() => void) | null>(null)
  const idRef = useRef(Math.max(0, ...(saved.current?.msgs ?? []).map((m) => m.id)) + 1)
  useEffect(() => { sset(sessionStorage, CONV_KEY, JSON.stringify({ msgs: msgs.slice(-40), suggestions, conv: conv.current })) }, [msgs, suggestions])
  const lastSaid = useRef<{ text: string; lang: Lang } | null>(null)
  const langRef = useRef(lang)
  langRef.current = lang
  const supportsMic = sttSupported()
  const supportsTts = ttsSupported()

  useEffect(() => onVoicesReady(() => setVoiceTick((n) => n + 1)), [])
  useEffect(() => { net.config().then((c) => setGeminiOn(c.saathi.providers.includes('gemini')), () => {}) }, [])
  const noVoice = useMemo(() => supportsTts && voiceTick >= 0 && !hasVoice(lang), [supportsTts, lang, voiceTick])

  const setVoiceOut = useCallback((v: boolean) => { setVoiceOutS(v); sset(localStorage, VOICE_KEY, v ? '1' : '0'); if (!v) { cancelTts.current?.(); cancelSpeech() } }, [])

  const say = useCallback((text: string, l: Lang) => {
    lastSaid.current = { text, lang: l }
    if (!voiceOut || !supportsTts) { setStatus('idle'); return }
    cancelTts.current?.()
    cancelTts.current = speak(text, l, {
      onStart: () => setStatus('speaking'),
      onBoundary: () => { setLevel(1); window.setTimeout(() => setLevel(0.25), 140) },
      onEnd: () => { setLevel(0); setStatus((s) => (s === 'speaking' ? 'idle' : s)) },
    })
    setStatus('speaking')
  }, [voiceOut, supportsTts])

  const apply = useCallback((turn: SaathiTurn) => {
    for (const a of turn.actions) {
      window.setTimeout(() => {
        if (a.type === 'set_language') setLang(a.lang)
        else if (a.type === 'navigate') navigate(a.to)
        else if (a.type === 'open_registration') navigate(`/network/camps/${a.camp_id}/register?${a.prefill.pin ? `pin=${a.prefill.pin}&` : ''}via=saathi`)
      }, 900)
    }
  }, [setLang])

  const send = useCallback(async (raw: string) => {
    const text = raw.trim().slice(0, 500)
    if (!text) return
    cancelTts.current?.(); cancelSpeech(); rec.current?.abort()
    setProblem(null); setInterim(''); setDraft(''); setSlow(false); setLevel(0)
    setMsgs((m) => [...m, { id: idRef.current++, role: 'user', text, lang: langRef.current }])
    setStatus('thinking')
    const slowTimer = window.setTimeout(() => setSlow(true), 6000)
    const route = parseNet(window.location.pathname, window.location.search)
    try {
      const turn = await net.saathi({ text, lang: langRef.current, state: conv.current, ui: { screen: route.name, ...(route.name === 'camp' || route.name === 'register' ? { camp_id: route.id } : {}) } })
      conv.current = turn.state
      setMsgs((m) => [...m, { id: idRef.current++, role: 'saathi', text: turn.reply.text, lang: turn.reply.lang, cards: turn.cards, links: turn.links }])
      setSuggestions(turn.suggestions)
      apply(turn)
      say(turn.reply.text, turn.reply.lang)
    } catch (e) {
      const offline = e instanceof NetError && (e.code === 'network' || e.code === 'timeout')
      setProblem(offline ? 'offline' : 'server')
      setMsgs((m) => [...m, { id: idRef.current++, role: 'saathi', text: t(offline ? 'saathi.offline' : 'saathi.serverError'), lang: langRef.current }])
      setStatus('idle')
    } finally { window.clearTimeout(slowTimer); setSlow(false) }
  }, [apply, say, t])

  const begin = useCallback(() => {
    cancelTts.current?.(); cancelSpeech()
    setProblem(null); setInterim(''); setStatus('listening')
    rec.current = startRecognition(langRef.current, {
      onInterim: setInterim,
      onSound: (on) => setLevel(on ? 0.8 : 0.2),
      onFinal: (h) => {
        if (h.confidence > 0 && h.confidence < 0.55) { setDraft(h.text); setProblem('low_confidence'); setStatus('idle'); setInterim(''); return }
        void send(h.text)
      },
      onError: (code) => {
        const map: Record<string, Problem> = { 'not-allowed': 'mic_denied', 'service-not-allowed': 'mic_denied', 'audio-capture': 'no_mic', network: 'stt_network', unsupported: 'stt_unsupported', 'no-speech': 'no_speech' }
        setProblem(map[code] ?? 'no_speech'); setStatus('idle'); setInterim(''); setLevel(0)
      },
      onEnd: (got) => { setLevel(0); if (!got) setStatus((s) => (s === 'listening' ? 'idle' : s)) },
    })
  }, [send])

  const listen = useCallback(() => {
    if (!supportsMic) { setProblem('stt_unsupported'); return }
    if (sget(sessionStorage, MIC_KEY) !== 'ok') { setConsentOpen(true); return }
    begin()
  }, [supportsMic, begin])

  const value = useMemo<Value>(() => ({
    status, level, msgs, suggestions, interim, problem, slow, voiceOut, setVoiceOut, supportsMic, supportsTts, noVoice, draft, setDraft,
    consentOpen, giveConsent: () => { sset(sessionStorage, MIC_KEY, 'ok'); setConsentOpen(false); begin() }, dismissConsent: () => setConsentOpen(false),
    geminiOn, send, listen,
    stopListening: () => { rec.current?.stop() },
    stopSpeaking: () => { cancelTts.current?.(); cancelSpeech(); setStatus('idle'); setLevel(0) },
    replay: () => { if (lastSaid.current) say(lastSaid.current.text, lastSaid.current.lang) },
    reset: () => { cancelTts.current?.(); cancelSpeech(); rec.current?.abort(); conv.current = {}; setMsgs([]); setSuggestions([]); setStatus('idle'); setProblem(null); setInterim('') },
    clearProblem: () => setProblem(null),
  }), [status, level, msgs, suggestions, interim, problem, slow, voiceOut, setVoiceOut, supportsMic, supportsTts, noVoice, draft, consentOpen, geminiOn, send, listen, begin, say])

  useEffect(() => () => { rec.current?.abort(); cancelSpeech() }, [])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useSaathi(): Value {
  const c = useContext(Ctx)
  if (!c) throw new Error('useSaathi outside provider')
  return c
}
