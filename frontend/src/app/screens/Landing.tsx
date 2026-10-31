import {
  ArrowRight, Camera, ClipboardCheck, Cpu, FileText, Gauge, HeartHandshake, Languages, Layers, RotateCcw, ScanEye, ShieldCheck, Stethoscope, Users, type LucideIcon,
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { IconCircle, cn } from '../../design/components'
import heroShot from '../../assets/landing/case_view.jpg'
import campImage from '../../assets/landing/screening_camp.webp'
import { BrandLockup } from '../BrandMark'
import { BRAND } from '../brand'
import { linkProps } from '../router'

// Public landing page. Every number on it is sourced: the statistics carry citations below, the model results come
// from the locked-evaluation file the About page also reads. The page makes no diagnostic claim; a clinician decides.

const NAV = [['#top', 'Home'], ['#product', 'Product'], ['#technology', 'Technology'], ['#impact', 'Impact'], ['#healthcare', 'For healthcare']] as const

type Locked = { sets: Record<string, { qwk: number; sensitivity: number; n_images: number; n_patients?: number }> }

export function Landing() {
  const [locked, setLocked] = useState<Locked | null>(null)
  useEffect(() => { document.title = `${BRAND} · AI-assisted retinal screening` }, [])
  useEffect(() => { fetch('/locked_results.json').then((r) => (r.ok ? r.json() : null)).then(setLocked, () => setLocked(null)) }, [])
  const L = locked?.sets

  return (
    <div id="top" className="ds ds-glow relative min-h-screen overflow-x-hidden text-text-primary">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-surface-card focus:px-4 focus:py-2">Skip to content</a>
      {/* Decorative retina-coloured glows at the page edges (CSS only). */}
      <span aria-hidden className="pointer-events-none absolute -left-[230px] top-[1020px] hidden h-[300px] w-[300px] rounded-full opacity-50 xl:block [background:radial-gradient(circle_at_60%_45%,#F7B48A,#E2622F_45%,#A8243F_80%,transparent_81%)] [filter:blur(2px)]" />
      <span aria-hidden className="pointer-events-none absolute -right-[260px] top-[60px] hidden h-[420px] w-[420px] rounded-full opacity-20 xl:block [background:radial-gradient(circle_at_40%_40%,#FBD3BC,#E2622F_55%,transparent_70%)]" />

      {/* Navigation */}
      <header className="relative mx-auto flex max-w-content items-center justify-between gap-4 px-4 py-5 md:px-8">
        <a {...linkProps('/')} aria-label={`${BRAND} home`} className="no-underline"><BrandLockup /></a>
        <nav aria-label="Sections" className="hidden items-center gap-8 lg:flex">
          {NAV.map(([to, label], i) => (
            <a key={to} href={to} aria-current={i === 0 ? 'page' : undefined}
              className={cn('relative text-body font-medium no-underline', i === 0 ? 'text-brand-700' : 'text-text-primary hover:text-brand-700')}>
              {label}
              {i === 0 && <span aria-hidden className="absolute -bottom-3 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full bg-brand-700" />}
            </a>
          ))}
          <a {...linkProps('/about')} className="text-body font-medium text-text-primary no-underline hover:text-brand-700">About</a>
        </nav>
        <a {...linkProps('/new')} className="inline-flex h-12 shrink-0 items-center gap-2 whitespace-nowrap rounded-full bg-cta px-6 text-section font-semibold text-text-onBrand no-underline shadow-lift hover:bg-cta-hover">
          Start screening<ArrowRight size={18} strokeWidth={2} aria-hidden />
        </a>
      </header>

      <main id="main" className="relative">
        {/* Hero */}
        <section aria-labelledby="hero-title" className="mx-auto grid max-w-content grid-cols-1 items-center gap-12 px-4 pb-12 pt-6 md:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:pt-10">
          <div>
            <p className="eyebrow">AI-assisted retinal screening</p>
            <h1 id="hero-title" className="mt-4 font-display text-[40px] leading-[1.05] sm:text-display lg:text-display-lg">
              Right patient, right specialist, <span className="text-accent-display">sooner.</span>
            </h1>
            <p className="mt-6 max-w-[34rem] text-lead text-text-secondary">
              {BRAND} supports early detection of diabetic retinopathy. It checks photo quality, suggests a stage, marks what it found and helps
              bring the right patient to the right specialist, so screening can reach more people. A clinician makes every decision.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a {...linkProps('/new')} className="inline-flex h-14 items-center gap-2 rounded-full bg-cta px-8 text-section font-semibold text-text-onBrand no-underline shadow-lift hover:bg-cta-hover">
                Start screening<ArrowRight size={18} strokeWidth={2} aria-hidden />
              </a>
              <a href="#how" className="inline-flex h-14 items-center gap-2 rounded-full border border-border-strong bg-surface-card px-8 text-section font-medium text-text-primary no-underline hover:bg-brand-50">
                See how it works
              </a>
            </div>
            <ul aria-label="What it does" className="mt-10 grid grid-cols-2 gap-x-4 gap-y-5 xl:grid-cols-4">
              <Feature icon={Camera} title="Quality check" body="before analysis" />
              <Feature icon={Gauge} title="AI-assisted" body="5-stage grading" />
              <Feature icon={FileText} title="Highlights key" body="retinal findings" />
              <Feature icon={Users} title="Supports" body="referral decisions" />
            </ul>
          </div>
          <figure className="m-0">
            <div className="rounded-xl border border-border-default bg-surface-card p-2 shadow-lift lg:[transform:perspective(1800px)_rotateY(-6deg)_rotateX(2deg)]">
              <img src={heroShot} alt={`${BRAND} case view: an IDRiD validation photograph with the AI-suggested stage, routing and detected findings`}
                className="block h-auto w-full rounded-card" width={1200} height={750} />
            </div>
            <figcaption className="mt-3 text-center text-caption text-text-muted">
              The real case view, captured from the app with an IDRiD validation image (CC BY 4.0), not a patient.
            </figcaption>
          </figure>
        </section>

        {/* Impact | photograph | how it works (one row on wide screens, as in the design) */}
        <section className="mx-auto grid max-w-content grid-cols-1 gap-10 px-4 py-12 md:px-8 lg:grid-cols-2 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1fr)_minmax(0,1.55fr)] xl:gap-8">
          <div id="impact" aria-labelledby="impact-title" className="scroll-mt-8">
            <p className="eyebrow">Our impact</p>
            <h2 id="impact-title" className="mt-3 font-display text-display-sm">Bringing specialist care closer</h2>
            <p className="mt-4 text-body text-text-secondary">
              Many people with diabetes are never screened for retinopathy until their vision changes. {BRAND} lets a trained health worker take a photograph,
              get an AI-assisted first read in seconds and send the cases that need it to an eye specialist first, especially in rural and underserved areas.
            </p>
            <a {...linkProps('/about')} className="mt-6 inline-flex h-12 items-center gap-2 rounded-full border border-brand-100 bg-brand-50 px-6 text-body font-semibold text-brand-800 no-underline hover:border-brand-700">
              Learn about our approach<ArrowRight size={16} strokeWidth={2} aria-hidden />
            </a>
          </div>

          <figure className="m-0">
            <div className="relative overflow-hidden rounded-xl shadow-lift">
              <img src={campImage} width={1400} height={788} loading="lazy"
                alt="Illustration: a health worker photographs an older woman's retina at a village screening camp; the image is reviewed by a clinician at a distant centre."
                className="block aspect-[4/3] h-auto w-full object-cover [object-position:28%_50%]" />
              <span aria-hidden className="absolute inset-y-0 right-0 w-1/2 [background:linear-gradient(270deg,rgba(35,26,22,0.55),transparent)]" />
              <figcaption className="absolute right-5 top-5 max-w-[11rem] text-right">
                <span className="block font-display text-[20px] italic leading-snug text-white [text-shadow:0_1px_8px_rgba(0,0,0,0.45)]">
                  Better screening. More people. Sooner care.
                </span>
                <span aria-hidden className="ml-auto mt-3 block h-[2px] w-10 bg-accent-display" />
              </figcaption>
            </div>
            <p className="mt-2 text-caption text-text-muted">Illustration, not a real patient or clinic.</p>
          </figure>

          <div id="how" aria-labelledby="how-title" className="scroll-mt-8 lg:col-span-2 xl:col-span-1">
            <p className="eyebrow">How {BRAND} works</p>
            <h2 id="how-title" className="mt-3 font-display text-display-sm">From image to insight in seconds</h2>
            <ol className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4 xl:gap-4">
              <Step n={1} icon={Camera} title="Image upload" body="Capture or upload a retinal fundus photograph." />
              <Step n={2} icon={Cpu} title="AI analysis" body="Quality check, grading and lesion detection." />
              <Step n={3} icon={FileText} title="Clear results" body="Stage, key findings and explanations." />
              <Step n={4} icon={Stethoscope} title="Specialist review" body="Helps prioritise high-risk patients." last />
            </ol>
          </div>
        </section>

        {/* Sourced statistics bar */}
        <section aria-labelledby="stats-title" className="mx-auto max-w-content px-4 pb-12 md:px-8">
          <h2 id="stats-title" className="sr-only">Why screening matters</h2>
          <div className="grid grid-cols-1 items-center gap-6 rounded-xl border border-border-default bg-surface-card/90 p-6 shadow-card md:grid-cols-2 xl:grid-cols-[1fr_1fr_auto] xl:divide-x xl:divide-border-default">
            <Stat icon={Users} value="101 million" body="people with diabetes in India" cite={1} />
            <Stat icon={ScanEye} value="1 in 8" body="of them has diabetic retinopathy" cite={2} />
            <div className="md:col-span-2 xl:col-span-1 xl:pl-6">
              <a href="#technology" className="inline-flex h-12 items-center gap-2 whitespace-nowrap rounded-full border border-brand-100 bg-brand-50 px-6 text-body font-semibold text-brand-800 no-underline hover:border-brand-700">
                Explore the evidence<ArrowRight size={16} strokeWidth={2} aria-hidden />
              </a>
            </div>
          </div>
          <ol className="mt-4 flex flex-col gap-1 pl-5 text-caption text-text-muted [list-style:decimal]">
            <li id="cite-1">Anjana RM et al. Metabolic non-communicable disease health report of India: the ICMR-INDIAB national cross-sectional study (ICMR-INDIAB-17). Lancet Diabetes Endocrinol 2023;11:474–89.</li>
            <li id="cite-2">Raman R et al. Prevalence of diabetic retinopathy in India stratified by known and undiagnosed diabetes, urban–rural locations, and socioeconomic indices: results from the SMART India population-based cross-sectional screening study. Lancet Glob Health 2022;10:e1764–73 (prevalence 12.5% among people with diabetes).</li>
          </ol>
        </section>

        {/* Technology */}
        <section id="technology" aria-labelledby="tech-title" className="mx-auto max-w-content scroll-mt-8 px-4 py-12 md:px-8">
          <p className="eyebrow">Technology</p>
          <h2 id="tech-title" className="mt-3 font-display text-display-sm lg:text-display">Measured honestly, on data it never saw</h2>
          <div id="product" className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-3">
            <TechCard icon={ScanEye} title="Grading model">
              A fine-tuned ConvNeXt network suggests the ICDR stage. On locked test sets it was evaluated once:
              {L?.idrid_test && L?.deepdrid
                ? ` agreement with specialists (QWK) ${L.idrid_test.qwk.toFixed(2)} on the IDRiD test and ${L.deepdrid.qwk.toFixed(2)} on DeepDRiD (${L.deepdrid.n_images.toLocaleString('en-GB')} images).`
                : ' results are on the About page.'}
            </TechCard>
            <TechCard icon={ShieldCheck} title="Knows when to defer">
              Calibrated confidence and a photo-quality check send uncertain or poor images to a person. The routine-rescreening pile is shown with its
              measured miss rate, including where it fell short on a locked test.
            </TechCard>
            <TechCard icon={Layers} title="Shows its reasons">
              Lesion maps for microaneurysms, haemorrhages and exudates, and sentences built only from measured findings. Hiding the lesions it cites lowers its score.
            </TechCard>
          </div>
        </section>

        {/* For healthcare */}
        <section id="healthcare" aria-labelledby="hc-title" className="mx-auto max-w-content scroll-mt-8 px-4 pb-16 pt-12 md:px-8">
          <div className="grid grid-cols-1 gap-8 rounded-xl border border-border-default bg-surface-card p-6 shadow-card md:p-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
            <div>
              <p className="eyebrow">For healthcare teams</p>
              <h2 id="hc-title" className="mt-3 font-display text-display-sm">Built for screening camps and clinics</h2>
            </div>
            <ul className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <Point icon={RotateCcw} title="Retake check at capture" body="Poor photographs are flagged with the reason while the patient is still there." />
              <Point icon={ClipboardCheck} title="Worklist by urgency" body="Expedited review first; routine rescreening last, with batch sign-off." />
              <Point icon={Languages} title="Patient summary in Hindi" body="Plain-language result for the patient, in English or Hindi." />
              <Point icon={HeartHandshake} title="Clinician in charge" body="Every result is confirmed or changed by a clinician." />
            </ul>
          </div>
        </section>
      </main>

      <footer className="relative border-t border-border-default bg-surface-card/70">
        <div className="mx-auto flex max-w-content flex-col gap-4 px-4 py-8 text-secondary text-text-secondary md:flex-row md:items-center md:justify-between md:px-8">
          <p className="max-w-[44rem]"><strong className="font-semibold text-text-primary">Research prototype, not a medical device.</strong> Final decisions are made by a clinician.
            It does not diagnose and is not validated for clinical use.
            <span className="mt-1 block">Fundus image: IDRiD, CC BY 4.0.</span></p>
          <a {...linkProps('/about')} className="font-medium text-text-link">Model card, data and licences</a>
        </div>
      </footer>
    </div>
  )
}

function Feature({ icon, title, body }: { icon: LucideIcon; title: string; body: string }) {
  return (
    <li className="flex items-center gap-3">
      <IconCircle icon={icon} />
      <span className="text-secondary leading-tight"><span className="block font-medium text-text-primary">{title}</span><span className="block text-text-secondary">{body}</span></span>
    </li>
  )
}

function Step({ n, icon, title, body, last }: { n: number; icon: LucideIcon; title: string; body: string; last?: boolean }) {
  return (
    <li className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <IconCircle icon={icon} size="lg" />
        <span className="text-secondary font-semibold text-accent-text">0{n}</span>
        {!last && <span aria-hidden className="hidden h-px flex-1 bg-accent-display/50 xl:block" />}
      </div>
      <div>
        <h3 className="text-section font-semibold">{title}</h3>
        <p className="mt-1 text-secondary text-text-secondary">{body}</p>
      </div>
    </li>
  )
}

function TechCard({ icon, title, children }: { icon: LucideIcon; title: string; children: ReactNode }) {
  return (
    <div className="rounded-card border border-border-default bg-surface-card p-6 shadow-card">
      <IconCircle icon={icon} />
      <h3 className="mt-4 text-section font-semibold">{title}</h3>
      <p className="mt-2 text-body text-text-secondary">{children}</p>
    </div>
  )
}

function Point({ icon, title, body }: { icon: LucideIcon; title: string; body: string }) {
  return (
    <li className="flex gap-3">
      <IconCircle icon={icon} size="sm" />
      <span><span className="block text-body font-semibold">{title}</span><span className="block text-secondary text-text-secondary">{body}</span></span>
    </li>
  )
}

function Stat({ icon, value, body, cite }: { icon: LucideIcon; value: string; body: string; cite: number }) {
  return (
    <div className="flex items-center gap-4 xl:px-6 xl:first:pl-0">
      <IconCircle icon={icon} />
      <p className="text-body text-text-secondary">
        <span className="block font-display text-display-sm leading-none text-text-primary">{value}<a href={`#cite-${cite}`} className="ml-1 align-super text-caption font-sans text-text-link" aria-label={`Source ${cite}`}>[{cite}]</a></span>
        <span className="mt-1 block">{body}</span>
      </p>
    </div>
  )
}
