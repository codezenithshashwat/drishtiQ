import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync, readdirSync } from 'node:fs'
import { renderToStaticMarkup } from 'react-dom/server'
import { Field, Input, Select, Segmented, ConfidenceBadge, ModalPanel } from '../src/design/components'
import { ImageViewer, type Layer } from '../src/app/screens/ImageViewer'
import { viewerGeometry } from '../src/app/viewerGeometry'
import { api, jpeg, png, type Analysis } from '../src/app/api'
import { parse, href, navigate } from '../src/app/router'
import theme from '../src/design/theme'
import shared from '../../design/tokens.json'

const analysis: Analysis = {
  status: 'ok', model_version: 'test-fixture', image: { width: 1024, height: 1024 },
  quality: { usable: true, issues: [], fov_fraction: .8, brightness: 100, sharpness: 100 },
  display_image: 'TEST_ORIGINAL', attribution: { method: 'Grad-CAM', overlay: 'TEST_CAM', note: 'Fixture attribution' },
  grading: { grade: 2, label: 'Moderate', low_confidence: false },
  lesions: [{ key: 'MA', name: 'Microaneurysms', color: '#CC79A7', components: 2, area_percent_of_field: .1, overlay: 'TEST_MA' }],
  findings: {
    landmarks: { optic_disc: { x: 200, y: 500, radius_px: 50 }, fovea: { x: 600, y: 500, uncertain: true }, disc_diameter_px: 100 },
    lesions: Object.fromEntries(['MA','HE','EX','SE'].map(key => [key, { name: key, count: 2, area_px: 10, per_quadrant: {}, regions: [] }])) as NonNullable<Analysis['findings']>['lesions'],
    haemorrhage_quadrants: { count: 0, quadrants: [], max_per_quadrant: 0 },
    macular_edema_risk: { level: 'low', reason: 'Fixture', nearest_exudate_dd: null, exudates_within_1dd: 0, landmarks_uncertain: true },
  },
}
const view = (layers: Set<Layer>, original = false, value = analysis) => renderToStaticMarkup(<ImageViewer analysis={value} eye="Right eye" layers={layers} original={original} onOriginal={() => {}} onMode={() => {}} onToggle={() => {}} name={k => k} />)

test('fit preserves aspect ratio and centers the photograph', () => {
  const v = viewerGeometry({ w: 1200, h: 800 }, { w: 600, h: 600 }, 1, { x: 0, y: 0 })
  assert.equal(v.width, 600); assert.equal(v.height, 400); assert.equal(v.pan.x, 0); assert.equal(v.pan.y, 0)
})
test('zoomed panning cannot lose the image outside the viewport', () => {
  const v = viewerGeometry({ w: 1000, h: 1000 }, { w: 600, h: 400 }, 2, { x: 9999, y: -9999 })
  assert.equal(v.pan.x, 100); assert.equal(v.pan.y, -200)
})
test('reset and narrow resizing clamp stale pan coordinates', () => {
  const v = viewerGeometry({ w: 1000, h: 1000 }, { w: 320, h: 500 }, 1, { x: 300, y: 300 })
  assert.equal(Math.abs(v.pan.x), 0); assert.equal(Math.abs(v.pan.y), 0)
})
test('portrait images fit without distortion', () => {
  const v = viewerGeometry({ w: 600, h: 1200 }, { w: 600, h: 400 }, 1, { x: 0, y: 0 })
  assert.equal(v.width, 200); assert.equal(v.height, 400)
})
test('field errors are connected to input and invalid state', () => {
  const html = renderToStaticMarkup(<Field id="reference" label="Patient reference" error="Enter a reference"><Input /></Field>)
  assert.match(html, /aria-describedby="reference-help"/); assert.match(html, /aria-invalid="true"/); assert.match(html, /id="reference-help" role="alert"/)
})
test('select hints and errors retain their accessible relationships', () => {
  const html = renderToStaticMarkup(<Field id="stage" label="Stage" error="Choose a stage"><Select><option>Choose</option></Select></Field>)
  assert.match(html, /<select[^>]+aria-describedby="stage-help"/); assert.match(html, /aria-invalid="true"/)
})
test('segmented control has exactly one keyboard tab stop', () => {
  const html = renderToStaticMarkup(<Segmented label="Mode" value="b" options={[{value:'a',label:'A'},{value:'b',label:'B'},{value:'c',label:'C'}]} />)
  assert.equal((html.match(/tabindex="0"/g) ?? []).length, 1); assert.equal((html.match(/tabindex="-1"/g) ?? []).length, 2)
})
test('high AI confidence is not styled as clinical success', () => {
  const html = renderToStaticMarkup(<ConfidenceBadge level="high" />)
  assert.match(html, /High confidence/); assert.doesNotMatch(html, /status-success/)
})
test('dialogs constrain their width and height to the viewport', () => {
  const html = renderToStaticMarkup(<ModalPanel title="Review" />)
  assert.match(html, /100vw-32px/); assert.match(html, /85dvh/)
})
test('original viewer excludes every predicted overlay', () => {
  const html = view(new Set(['MA','cam']), true)
  assert.match(html, /TEST_ORIGINAL/); assert.doesNotMatch(html, /TEST_MA|TEST_CAM/)
})
test('lesion mode only displays selected segmentation layers', () => {
  const html = view(new Set(['MA']))
  assert.match(html, /TEST_MA/); assert.doesNotMatch(html, /TEST_CAM/); assert.match(html, /not confirmed lesions/)
})
test('attribution mode does not combine segmentation with Grad-CAM', () => {
  const html = view(new Set(['MA','cam']))
  assert.match(html, /TEST_CAM/); assert.doesNotMatch(html, /TEST_MA/); assert.match(html, /not a lesion detector/)
})
test('rejected images have no available AI overlay controls', () => {
  const html = view(new Set(), true, { ...analysis, status: 'rejected', findings: undefined, attribution: undefined, lesions: undefined })
  assert.doesNotMatch(html, /TEST_MA|TEST_CAM/); assert.match(html, /disabled=""[^>]*>Lesions/)
})
test('clinical overlay and severity palettes are unchanged', () => {
  for (const key of ['lesion','heatmap','landmark','stage'] as const) assert.deepEqual(theme.color[key], shared.color[key])
})
function luminance(hex: string) {
  const c = [1,3,5].map(i => parseInt(hex.slice(i,i+2),16)/255).map(v => v <= .04045 ? v/12.92 : ((v+.055)/1.055)**2.4)
  return c[0]*.2126+c[1]*.7152+c[2]*.0722
}
function contrast(a: string,b: string) { const x=luminance(a),y=luminance(b); return (Math.max(x,y)+.05)/(Math.min(x,y)+.05) }
test('UI text, primary actions and form boundaries meet contrast thresholds', () => {
  for(const text of [theme.color.text.primary,theme.color.text.secondary,theme.color.text.muted]) for(const bg of [theme.color.surface.card,theme.color.surface.page,theme.color.surface.subtle]) assert.ok(contrast(text,bg)>=4.5, `${text} on ${bg}`)
  assert.ok(contrast('#FFFFFF',theme.color.brand['700'])>=4.5)
  assert.ok(contrast(theme.color.border.strong,theme.color.surface.card)>=3)
  assert.ok(contrast(theme.color.focus,theme.color.surface.card)>=3)
})
test('existing deep links, reports and review filters retain route contracts', () => {
  assert.deepEqual(parse('/app/cases/RS%2D42'),{name:'case',id:'RS-42'})
  assert.deepEqual(parse('/app/worklist','?tab=reviewed&q=ABC'),{name:'worklist',tab:'reviewed',q:'ABC'})
  assert.deepEqual(parse('/app/patients/A%20B/report','?case=RS-42'),{name:'report',patient:'A B',caseId:'RS-42'})
  assert.equal(href('/new'),'/app/new'); assert.equal(href('/'),'/')
})
test('image sources and report URLs preserve their encodings', () => {
  assert.equal(jpeg('data:image/jpeg;base64,x'),'data:image/jpeg;base64,x')
  assert.equal(png('abc'),'data:image/png;base64,abc')
  assert.equal(api.reportUrl('A/B','patient','hi','pdf'),'/api/patients/A%2FB/report.pdf?kind=patient&lang=hi')
})
test('cancelled draft navigation does not change browser history', () => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'window')
  const target = new EventTarget()
  target.addEventListener('drishtiq:before-navigate', event => event.preventDefault())
  Object.defineProperty(globalThis, 'window', { configurable: true, value: Object.assign(target, {
    history: { pushState: () => assert.fail('Cancelled navigation changed history') },
  }) })
  try { navigate('/worklist') } finally {
    if (previous) Object.defineProperty(globalThis, 'window', previous)
    else Reflect.deleteProperty(globalThis, 'window')
  }
})
test('screening and review requests retain the backend contract (mock fetch only)', async () => {
  const original = globalThis.fetch
  const requests: {url: string; init?: RequestInit}[] = []
  globalThis.fetch = async (url, init) => { requests.push({url:String(url),init}); return new Response('{}',{status:200}) }
  try {
    await api.createCase(new File(['fixture'],'retina.png',{type:'image/png'}),'TEST-ONLY','left',{vision_problems:true,prior_treatment:false})
    assert.equal(requests[0].url,'/api/cases'); assert.equal(requests[0].init?.method,'POST')
    const body=requests[0].init?.body as FormData
    assert.equal(body.get('patient_ref'),'TEST-ONLY'); assert.equal(body.get('eye'),'left'); assert.equal(body.get('vision_problems'),'true'); assert.equal(body.get('prior_treatment'),'false')
    // V3: no reviewer field (identity comes from the session), an explicit next action, and the CSRF header on every call.
    const review={decision:'disagree',corrected_stage:3,corrected_dme:null,next_action:'urgent_referral' as const,note:'Fixture'}
    await api.review('CASE/1',review)
    assert.equal(requests[1].url,'/api/cases/CASE%2F1/review'); assert.deepEqual(JSON.parse(requests[1].init?.body as string),review)
    for (const r of requests) assert.equal(new Headers(r.init?.headers).get('X-Requested-With'),'dqn')
    assert.equal(requests[1].init?.credentials,'same-origin')
  } finally { globalThis.fetch=original }
})
test('production assets stay local, including display fonts', () => {
  const assets = new URL('../dist/assets/', import.meta.url)
  const html=readFileSync(new URL('../dist/index.html', import.meta.url),'utf8')
  assert.doesNotMatch(html, /(?:src|href)\s*=\s*["'](?:https?:)?\/\//i)
  for(const file of readdirSync(assets).filter(f=>f.endsWith('.css'))) assert.doesNotMatch(readFileSync(new URL(file, assets),'utf8'), /url\(\s*["']?(?:https?:)?\/\//i)
  assert.ok(readdirSync(assets).some(f=>f.includes('dm-serif-display') && f.endsWith('.woff2')))
})
