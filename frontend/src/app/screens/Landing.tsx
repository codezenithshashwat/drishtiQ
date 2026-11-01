import { ArrowDown, ArrowRight, ArrowUpRight, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import campImage from '../../assets/landing/screening_camp.webp'
import { BrandLockup } from '../BrandMark'
import { BRAND } from '../brand'
import { linkProps } from '../router'
import { EyeFilm } from './EyeFilm'
import { WorkflowPreview } from './WorkflowPreview'
import './landing.css'

type Locked = { sets: Record<string, { qwk: number; sensitivity: number; n_images: number }> }
const studies = [
  { key: 'idrid_test', title: 'IDRiD clean test', context: 'Locked benchmark evaluation', limit: 'The routine-routing safety target was not met. Five referable eyes were routed to routine. Clinician review remains essential.' },
  { key: 'deepdrid', title: 'DeepDRiD', context: 'Locked external evaluation', limit: 'External evaluation is useful evidence, but it does not establish safety in rural screening or across every camera and population.' },
] as const

export function Landing() {
  const [locked, setLocked] = useState<Locked | null>(null)
  const [evidenceState, setEvidenceState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [study, setStudy] = useState(0)
  const [section, setSection] = useState('')
  useEffect(() => {
    document.title = BRAND + ' · For eye specialists'
    const controller = new AbortController()
    fetch('/locked_results.json', { signal: controller.signal }).then(r => { if (!r.ok) throw new Error('Unavailable'); return r.json() }).then(data => { setLocked(data); setEvidenceState('ready') }, error => { if (error.name !== 'AbortError') setEvidenceState('error') })
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) setSection(entry.target.id)
    }, { rootMargin: '-15% 0px -55% 0px', threshold: 0 })
    document.querySelectorAll('[data-landing-section]').forEach(el => observer.observe(el))
    return () => { controller.abort(); observer.disconnect() }
  }, [])
  const selected = studies[study]
  const result = locked?.sets[selected.key]

  return <div id="top" className="ds landing landing-cinematic">
    <a href="#main-content" className="skip-link">Skip to content</a>
    <header className="landing-header">
      <a {...linkProps('/specialists')} aria-label={BRAND + ' for eye specialists'} className="landing-brand"><BrandLockup /></a>
      <nav aria-label="Sections">
        {[['workflow', 'The experience'], ['evidence', 'The evidence'], ['access', 'The purpose']].map(([id, label]) => <a key={id} href={'#' + id} aria-current={section === id ? 'location' : undefined}>{label}</a>)}
      </nav>
      <span className="landing-header-links"><a {...linkProps('/')} className="landing-patients">For patients</a><a {...linkProps('/worklist')} className="landing-workspace">Specialist workspace<ArrowUpRight size={17} aria-hidden /></a></span>
    </header>
    <main id="main-content" tabIndex={-1}>
      <section className="vision-hero" aria-labelledby="hero-title" data-landing-section id="vision">
        <EyeFilm />
        <div className="vision-copy">
          <h1 id="hero-title">Every eye.<br />A closer look.</h1>
          <p className="vision-lead">Retinal intelligence.<br />Human judgment.</p>
          <p className="vision-description">AI-assisted diabetic retinopathy screening. From the first photograph to the clinician's next decision.</p>
          <div className="vision-actions">
            <a {...linkProps('/new')} className="vision-button">Start a screening<span><ArrowUpRight size={20} aria-hidden /></span></a>
            <a href="#workflow" className="vision-explore">Explore the experience<ArrowDown size={17} aria-hidden /></a>
          </div>
          <p className="vision-disclaimer">Research prototype. Clinician review required.</p>
        </div>
        <div className="vision-footer">
          <a href="#workflow"><span>Photograph</span><ArrowRight size={16} aria-hidden /><span>Evidence</span><ArrowRight size={16} aria-hidden /><span>Clinical review</span></a>
          <span>Designed around the person behind the image.</span>
        </div>
      </section>
      <section id="workflow" data-landing-section className="experience-section landing-section" aria-labelledby="workflow-title">
        <div className="section-intro">
          <h2 id="workflow-title">A clearer path<br />through the evidence.</h2>
          <p>One connected workspace. Explore how a retinal photograph moves from screening to clinical review.</p>
        </div>
        <WorkflowPreview />
      </section>
      <section id="evidence" data-landing-section className="evidence-section" aria-labelledby="evidence-title">
        <div className="landing-section evidence-layout">
          <div className="evidence-copy">
            <h2 id="evidence-title">Confidence begins<br />with transparency.</h2>
            <p>The frozen prototype was evaluated on locked test data. You can inspect the results, the methods and the errors that matter.</p>
            <a {...linkProps('/about')} className="editorial-link">Explore model information<ArrowUpRight size={18} aria-hidden /></a>
          </div>
          <div className="study-panel">
            <div className="study-tabs" role="group" aria-label="Evaluation dataset">
              {studies.map((s, i) => <button key={s.key} type="button" aria-pressed={study === i} onClick={() => setStudy(i)}>{s.title}</button>)}
            </div>
            <div className="study-result" aria-live="polite" aria-atomic="true">
              <p className="study-context">{selected.context}</p>
              <dl>
                <div><dt>Grading agreement <abbr title="Quadratic weighted kappa">QWK</abbr></dt><dd>{result?.qwk.toFixed(3) ?? '—'}</dd></div>
                <div><dt>Evaluated images</dt><dd>{result?.n_images.toLocaleString('en-GB') ?? '—'}</dd></div>
              </dl>
              <p className="study-explanation">{evidenceState === 'error' ? 'Recorded results could not be loaded. See model information for availability.' : evidenceState === 'loading' ? 'Loading recorded evaluation…' : 'QWK measures agreement across ordered severity stages. It is not percentage accuracy.'}</p>
              <p className="study-limit"><ShieldCheck size={20} aria-hidden /><span>{selected.limit}</span></p>
            </div>
          </div>
        </div>
      </section>
      <section id="access" data-landing-section className="access-section landing-section" aria-labelledby="access-title">
        <figure className="access-picture"><img src={campImage} width={1400} height={788} loading="lazy" alt="Illustration of a retinal screening camp in a village clinic" /><figcaption>Illustration of the intended setting; not a clinical deployment.</figcaption></figure>
        <div className="access-copy">
          <h2 id="access-title">Behind every image,<br />a person waiting<br />to be seen.</h2>
          <p>Specialist attention is precious. Catching poor photographs early and organising the review queue can help screening teams use that time well.</p>
          <p>Individual and batch screening. A prioritised worklist. Patient summaries in English and Hindi. Built around a real workflow, with real-world validation still ahead.</p>
          <a {...linkProps('/new')} className="landing-solid-button">Begin with a photograph<ArrowUpRight size={19} aria-hidden /></a>
          <p style={{ marginTop: 20 }}><a {...linkProps('/')} className="editorial-link">For patients and families: Saathi and eye camps<ArrowUpRight size={18} aria-hidden /></a></p>
        </div>
      </section>
      <section className="landing-closing">
        <div><h2>See more. Review thoughtfully.</h2><p>Open the specialist workspace and follow the evidence.</p></div>
        <a {...linkProps('/worklist')} className="vision-button">Enter DrishtiQ<span><ArrowUpRight size={22} aria-hidden /></span></a>
      </section>
    </main>
    <footer className="landing-footer">
      <div><BrandLockup /><p>Research prototype, not a medical device. Not validated for clinical use. A qualified clinician makes the final decision.</p></div>
      <div className="footer-links"><a {...linkProps('/')}>For patients<ArrowUpRight size={14} aria-hidden /></a><a {...linkProps('/about')}>Model, data & licences<ArrowUpRight size={14} aria-hidden /></a><a href="https://www.vidsplay.com/eye-free-stock-video/" target="_blank" rel="noreferrer">Eye footage: Vidsplay<ArrowUpRight size={14} aria-hidden /></a><a href="#top">Back to top<ArrowUpRight size={14} aria-hidden /></a></div>
    </footer>
  </div>
}
