import { ArrowUpRight, Camera, Check, ChevronRight, FileText, Focus, Layers, Minus, Plus, Stethoscope } from 'lucide-react'
import { useId, useState } from 'react'
import heroShot from '../../assets/landing/case_view.jpg'
import tokens from '../../../../design/tokens.json'
import { linkProps } from '../router'

const steps = [
  { title: 'Start with a clear photograph', short: 'Capture', icon: Camera, description: 'Add a photograph for each eye. Quality checks help flag images that may need a retake while the person is still there.', action: 'Open new screening', path: '/new' },
  { title: 'Look closer at the evidence', short: 'Inspect', icon: Layers, description: 'Inspect the original, predicted lesion regions and Grad-CAM separately. Zoom in, compare views and adjust overlays in the case viewer.', action: 'Open the clinical worklist', path: '/worklist' },
  { title: 'Keep clinical judgment central', short: 'Review', icon: Stethoscope, description: 'Review the AI suggestion alongside the photograph. Record agreement, a correction or an ungradable image. The clinician decides.', action: 'Open the review queue', path: '/worklist' },
  { title: 'Make the next conversation easier', short: 'Report', icon: FileText, description: 'Open a doctor report or a patient summary in English or Hindi. Keep the model evidence and the limitations visible.', action: 'Find a case to report', path: '/worklist' },
] as const

export function WorkflowPreview() {
  const [active, setActive] = useState(1)
  const [zoom, setZoom] = useState(1)
  const id = useId()
  const step = steps[active]
  return <div className="workflow-explorer">
    <div className="workflow-selector">
      <ol aria-label="Explore the screening workflow">
        {steps.map((s, index) => <li key={s.short} data-active={active === index}>
          <button type="button" aria-expanded={active === index} aria-controls={`${id}-${index}`} onClick={() => setActive(index)}>
            <span className="workflow-number">0{index + 1}</span><span>{s.short}</span><ChevronRight size={20} aria-hidden />
          </button>
          <div id={`${id}-${index}`} hidden={active !== index} className="workflow-description"><h3>{s.title}</h3><p>{s.description}</p></div>
        </li>)}
      </ol>
      <a {...linkProps(step.path)} className="editorial-link">{step.action}<ArrowUpRight size={18} aria-hidden /></a>
    </div>
    <div className="workflow-stage">
      <div className="preview-bar"><span><step.icon size={17} aria-hidden />{step.short} workspace</span><span>Interactive overview</span></div>
      <div className="workflow-canvas" data-step={active}>
        {active === 0 ? <div className="capture-preview">
          <Focus size={52} strokeWidth={1} aria-hidden /><h3>Begin with the right image.</h3><p>Upload a retinal fundus photograph, not an external photograph of an eye.</p>
          <a {...linkProps('/new')} className="preview-upload"><Camera size={22} aria-hidden /><span>Select retinal photographs<small>Open the screening form</small></span><ArrowUpRight size={20} aria-hidden /></a>
          <div className="capture-checks"><span><Check size={15} aria-hidden />Patient reference</span><span><Check size={15} aria-hidden />Eye identification</span></div>
        </div> : active === 3 ? <div className="report-preview">
          <FileText size={40} strokeWidth={1.25} aria-hidden /><h3>One case.<br />Two conversations.</h3>
          <div><p><strong>For the clinician</strong>Grading, image quality and predicted findings.</p><p><strong>For the patient</strong>A plain-language summary in English or Hindi.</p></div>
          <p className="preview-note">Signed clinician decisions set the next action in reports. The original AI suggestion stays visible for comparison.</p>
        </div> : <>
          <figure className="example-retina">
            <div className="example-retina-crop"><div className="retinal-plate" style={{ transform: `scale(${zoom})` }}><img src={heroShot} width={1200} height={750} loading="lazy" alt="Recorded IDRiD example with predicted lesion regions already drawn on the retinal photograph" /></div></div>
            <figcaption>Recorded example · IDRiD validation image</figcaption>
          </figure>
          <div className="example-toolbar"><span>Explore the example</span><div role="group" aria-label="Example image magnification"><button type="button" aria-label="Zoom example out" disabled={zoom <= 1} onClick={() => setZoom(z => Math.max(1, z - .25))}><Minus size={16} /></button><output aria-label="Example magnification">{zoom.toFixed(2)}×</output><button type="button" aria-label="Zoom example in" disabled={zoom >= 2} onClick={() => setZoom(z => Math.min(2, z + .25))}><Plus size={16} /></button></div></div>
          {active === 1 ? <div className="example-legend">{(['MA', 'HE', 'EX', 'SE'] as const).map(k => <span key={k}><i style={{ background: tokens.color.lesion[k] }} aria-hidden />{k}</span>)}<span>Predicted regions</span></div> : <p className="example-review-note"><Stethoscope size={20} aria-hidden />An AI suggestion is a starting point for review. It is not a final diagnosis.</p>}
        </>}
      </div>
      <p className="workflow-footnote">{active === 1 ? 'This recorded example has fixed overlays, not live inference. Grad-CAM in the case viewer shows model attribution, not proof of disease.' : active === 2 ? 'Signed clinician decisions govern the next action in reports and linked patient status. AI suggestions stay provisional.' : 'Product overview. No patient data is submitted from this preview.'}</p>
    </div>
  </div>
}
