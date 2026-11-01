import { CalendarDays, MapPin, Mic, RotateCcw, Send, ShieldCheck, Square, Volume2, VolumeX } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { linkProps } from '../../app/router'
import type { SaathiCard } from '../api'
import { SaathiOrb, Wave } from '../components/SaathiOrb'
import { Btn, Modal, Notice, VerificationBadge } from '../components/ui'
import { useI18n } from '../i18n/I18n'
import type { Key } from '../i18n/strings'
import { useSaathi, type Msg } from '../saathi/SaathiProvider'

function Cards({ cards }: { cards: SaathiCard[] }) {
  const { t, when } = useI18n()
  return (
    <>
      {cards.map((c, i) => {
        if (c.type === 'camps') return (
          <div key={i} className="nw-thread" style={{ gap: 10 }}>
            {c.items.map((x) => (
              <a key={x.id} className="nw-mini" {...linkProps(`/network/camps/${x.id}`)}>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <b>{x.title}</b>
                  <small style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 4 }}>
                    <span style={{ display: 'inline-flex', gap: 5, alignItems: 'center' }}><CalendarDays size={14} aria-hidden />{when(x.starts_at)}</span>
                    <span style={{ display: 'inline-flex', gap: 5, alignItems: 'center' }}><MapPin size={14} aria-hidden />{x.village}, {x.district}</span>
                  </small>
                  <span style={{ display: 'inline-flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}><VerificationBadge v={x.verification} />{x.state !== 'open' && <span className="nw-badge neutral">{t(`state.${x.state}` as Key)}</span>}</span>
                </span>
              </a>
            ))}
          </div>
        )
        if (c.type === 'topic') return (
          <a key={i} className="nw-mini" {...linkProps(`/network/learn/${c.slug}`)}><span><b>{c.title}</b><small>{t('learn.illustrative')}</small></span></a>
        )
        if (c.type === 'registrations') return (
          <div key={i} className="nw-thread" style={{ gap: 10 }}>{c.items.map((r) => (
            <a key={r.ref} className="nw-mini" {...linkProps('/network/me')}><span><b>{r.title}</b><small>{when(r.starts_at, false)} · {r.status_label}</small></span></a>
          ))}</div>
        )
        return null
      })}
    </>
  )
}

function Bubble({ m }: { m: Msg }) {
  const { t } = useI18n()
  return (
    <div className={`nw-msg ${m.role}`}>
      {m.role === 'saathi' && <span className="who"><ShieldCheck size={13} aria-hidden />{t('saathi.name')}</span>}
      <div className="bub" lang={m.lang}>{m.text}</div>
      {m.cards && <Cards cards={m.cards} />}
      {m.links && m.links.length > 0 && <div className="nw-sugg">{m.links.map((l) => <Btn key={l.to} variant="secondary" size="sm" to={l.to}>{l.label}</Btn>)}</div>}
    </div>
  )
}

export function SaathiScreen() {
  const { t, lang } = useI18n()
  const s = useSaathi()
  const [text, setText] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)
  useEffect(() => { if (s.draft) { setText(s.draft); input.current?.focus() } }, [s.draft])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'end' }) }, [s.msgs.length, s.status])

  const submit = (e: FormEvent) => { e.preventDefault(); const v = text.trim(); if (!v) return; setText(''); void s.send(v) }
  const onOrb = () => { if (s.status === 'listening') s.stopListening(); else if (s.status === 'speaking') { s.stopSpeaking(); s.listen() } else if (s.status === 'idle') s.listen() }
  const caption = s.status === 'idle' ? (s.supportsMic ? t('saathi.tapToTalk') : t('saathi.typeBelow')) : t(`saathi.state.${s.status}` as Key)
  const problemKey: Record<string, Key> = { mic_denied: 'saathi.p.micDenied', no_mic: 'saathi.p.noMic', no_speech: 'saathi.p.noSpeech', stt_network: 'saathi.p.sttNetwork', stt_unsupported: 'saathi.p.unsupported', low_confidence: 'saathi.p.lowConfidence', offline: 'saathi.p.offline', server: 'saathi.p.server' }

  return (
    <div className="wrap">
      <div className="nw-saathi">
        <section className="stagebox" aria-label={t('nav.saathi')}>
          <p className="eyebrow">{t('saathi.name')} · {t('saathi.sub')}</p>
          <SaathiOrb state={s.status} level={s.level} size={188} onClick={onOrb} label={s.status === 'listening' ? t('saathi.orbStop') : t('saathi.orbTalk')} />
          <p className="nw-caption" aria-live="polite">{caption}{s.slow && <span className="muted" style={{ fontWeight: 400 }}> · {t('saathi.slow')}</span>}</p>
          <div style={{ minHeight: 28, display: 'grid', placeItems: 'center' }}>
            {s.status === 'speaking' ? <Wave on /> : s.status === 'listening' ? <p className="nw-interim" aria-live="polite">{s.interim || t('saathi.listeningHint')}</p> : null}
          </div>
          <div className="nw-tools">
            {s.status === 'listening' && <Btn variant="secondary" size="sm" icon={Square} onClick={s.stopListening}>{t('saathi.done')}</Btn>}
            {s.status === 'speaking' && <Btn variant="secondary" size="sm" icon={Square} onClick={s.stopSpeaking}>{t('saathi.stop')}</Btn>}
            {s.status === 'idle' && s.msgs.length > 0 && <Btn variant="secondary" size="sm" icon={Volume2} onClick={s.replay}>{t('saathi.replay')}</Btn>}
            {s.supportsTts && <Btn variant="ghost" size="sm" icon={s.voiceOut ? Volume2 : VolumeX} aria-pressed={s.voiceOut} onClick={() => s.setVoiceOut(!s.voiceOut)}>{s.voiceOut ? t('saathi.voiceOn') : t('saathi.voiceOff')}</Btn>}
            {s.msgs.length > 0 && <Btn variant="ghost" size="sm" icon={RotateCcw} onClick={s.reset}>{t('saathi.newChat')}</Btn>}
          </div>
        </section>

        {s.problem && (
          <Notice tone={s.problem === 'low_confidence' ? 'info' : 'warn'} title={s.problem === 'mic_denied' ? t('saathi.p.micDeniedT') : undefined}
            action={s.problem === 'mic_denied' || s.problem === 'stt_unsupported' ? undefined : <Btn variant="ghost" size="sm" onClick={s.clearProblem}>{t('common.dismiss')}</Btn>}>
            {t(problemKey[s.problem])}
          </Notice>
        )}
        {s.noVoice && s.voiceOut && <Notice tone="info">{t('saathi.noVoice')}</Notice>}

        <section className="nw-thread" aria-label={t('saathi.conversation')} aria-live="polite" aria-relevant="additions">
          {s.msgs.length === 0 && (
            <div className="nw-msg saathi"><span className="who"><ShieldCheck size={13} aria-hidden />{t('saathi.name')}</span><div className="bub" lang={lang}>{t('saathi.greeting')}</div></div>
          )}
          {s.msgs.map((m) => <Bubble key={m.id} m={m} />)}
          {s.status === 'thinking' && <div className="nw-msg saathi"><div className="bub" aria-hidden>···</div></div>}
          <div ref={endRef} />
        </section>

        <div className="nw-sugg" aria-label={t('saathi.try')}>
          {(s.suggestions.length ? s.suggestions : [t('saathi.s1'), t('saathi.s2'), t('saathi.s3')]).map((q) => <button type="button" key={q} onClick={() => void s.send(q)}>{q}</button>)}
        </div>

        <form className="nw-compose" onSubmit={submit}>
          <input ref={input} value={text} onChange={(e) => setText(e.target.value)} placeholder={t('saathi.placeholder')} aria-label={t('saathi.placeholder')} maxLength={500} enterKeyHint="send" />
          {s.supportsMic && <Btn type="button" variant={s.status === 'listening' ? 'saffron' : 'secondary'} size="sm" icon={s.status === 'listening' ? Square : Mic} onClick={onOrb} aria-label={t('saathi.orbTalk')}>{s.status === 'listening' ? t('saathi.done') : t('saathi.mic')}</Btn>}
          <Btn type="submit" size="sm" icon={Send} disabled={!text.trim()}>{t('saathi.send')}</Btn>
        </form>
        <p className="muted" style={{ fontSize: '.82rem', textAlign: 'center' }}>{t('saathi.privacy')}{s.geminiOn ? ` ${t('saathi.geminiNote')}` : ''}</p>
      </div>

      {s.consentOpen && (
        <Modal title={t('saathi.consentTitle')} onClose={s.dismissConsent}>
          <p>{t('saathi.consentBody')}</p>
          <ul style={{ display: 'grid', gap: 8, color: 'var(--ink2)', fontSize: '.95rem' }}>
            <li>• {t('saathi.consent1')}</li><li>• {t('saathi.consent2')}</li><li>• {t('saathi.consent3')}</li>
          </ul>
          <div style={{ display: 'grid', gap: 10 }}>
            <Btn size="lg" onClick={s.giveConsent}>{t('saathi.consentYes')}</Btn>
            <Btn variant="ghost" onClick={s.dismissConsent}>{t('saathi.consentNo')}</Btn>
          </div>
        </Modal>
      )}
    </div>
  )
}
