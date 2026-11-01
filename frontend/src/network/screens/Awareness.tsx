import { Mic, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { linkProps } from '../../app/router'
import { net, type Topic as TopicT } from '../api'
import { topicBg, TopicArt } from '../components/art'
import { Btn, Loading, Notice, PageHead, ReadAloud, Reveal } from '../components/ui'
import { useI18n } from '../i18n/I18n'
import { BackLink } from './Camps'

export function Awareness() {
  const { t, lang, errMsg } = useI18n()
  const [items, setItems] = useState<TopicT[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { let live = true; setItems(null); net.topics(lang).then((r) => live && setItems(r.items), (e) => live && setErr(errMsg(e))); return () => { live = false } }, [lang, errMsg])
  return (
    <>
      <PageHead eyebrow={t('nav.learn')} title={t('learn.title')} lead={t('learn.lead')} />
      <div className="wrap" style={{ display: 'grid', gap: 24, paddingBottom: 56 }}>
        <Notice tone="warn" title={t('learn.illustrative')}>{t('learn.illustrativeBody')}</Notice>
        {err && <Notice tone="danger" title={t('common.errorTitle')}>{err}</Notice>}
        {!items && !err && <Loading />}
        {items && (
          <div className="nw-grid c3">
            {items.map((x, i) => (
              <Reveal key={x.slug} delay={i * 60}>
                <a className="nw-topic" {...linkProps(`/network/learn/${x.slug}`)} style={{ height: '100%' }}>
                  <div className="pic" style={{ background: topicBg(x.slug)[0] }}><TopicArt slug={x.slug} /></div>
                  <div className="body"><h2 style={{ fontSize: '1.2rem', lineHeight: 1.3 }}>{x.title}</h2><p>{x.summary}</p><span className="muted" style={{ fontWeight: 600, color: 'var(--brand)' }}>{t('learn.read')} →</span></div>
                </a>
              </Reveal>
            ))}
          </div>
        )}
      </div>
    </>
  )
}

export function Topic({ slug }: { slug: string }) {
  const { t, lang, errMsg } = useI18n()
  const [topic, setTopic] = useState<TopicT | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { let live = true; setTopic(null); net.topic(slug, lang).then((r) => live && setTopic(r), (e) => live && setErr(errMsg(e))); return () => { live = false } }, [slug, lang, errMsg])
  const back = <BackLink to="/network/learn" label={t('learn.title')} />
  if (err) return <div className="wrap" style={{ padding: '32px 20px' }}>{back}<Notice tone="danger" title={t('common.errorTitle')}>{err}</Notice></div>
  if (!topic) return <div className="wrap" style={{ padding: '32px 20px' }}>{back}<Loading /></div>
  const spoken = [topic.title, topic.summary, ...(topic.blocks ?? []).map((b) => `${b.h}. ${b.p}`)].join('. ')
  return (
    <article>
      <div style={{ background: topicBg(slug)[0] }}>
        <div className="wrap" style={{ padding: '20px 20px 0' }}>
          {back}
          <div style={{ maxWidth: 720, margin: '0 auto', height: 'clamp(150px,30vw,260px)' }}><TopicArt slug={slug} size="hero" /></div>
        </div>
      </div>
      <div className="narrow" style={{ padding: '32px 20px 64px', display: 'grid', gap: 22 }}>
        <h1 className="display" style={{ fontSize: 'clamp(1.9rem,4.4vw,2.8rem)' }}>{topic.title}</h1>
        <p className="lead" style={{ fontSize: '1.2rem' }}>{topic.summary}</p>
        <div><ReadAloud text={spoken} lang={lang} /></div>
        <div style={{ display: 'grid', gap: 14 }}>{(topic.blocks ?? []).map((b) => <section key={b.h} className="nw-block"><h2 style={{ fontSize: '1.12rem' }}>{b.h}</h2><p>{b.p}</p></section>)}</div>
        <Notice tone="warn" title={t('learn.illustrative')}>{t('learn.generalNote')}</Notice>
        <div className="nw-card tint" style={{ display: 'grid', gap: 14 }}>
          <h2 className="display" style={{ fontSize: '1.5rem' }}>{t('learn.nextTitle')}</h2>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}><Btn size="lg" icon={Search} to="/network/camps">{t('home.ctaCamps')}</Btn><Btn variant="secondary" size="lg" icon={Mic} to="/network/saathi">{t('home.ctaTalk')}</Btn></div>
        </div>
      </div>
    </article>
  )
}
