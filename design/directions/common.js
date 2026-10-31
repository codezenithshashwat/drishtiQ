// Shared, static rendering helpers for the design directions (no animation). Data: data/case.js (window.CASE).
const C = window.CASE, G = window.GLOSSARY, F = C.findings
const LESIONS = ['MA', 'HE', 'EX', 'SE']
// Okabe-Ito, colour-blind safe (same as the app).
const LESION_COLOR = { MA: '#E69F00', HE: '#D55E00', EX: '#F0E442', SE: '#56B4E9' }
// Severity: text + colour, never colour alone.
const STAGE_COLOR = ['#1D7A4D', '#3A7CA5', '#B7791F', '#C2410C', '#A4262C']
const SELECTED = 'he-quadrants' // statically "selected" sentence, to show the highlight state

function stagePlain(g) { return G['stage' + g].plain }
function stageClinical(g) { return G['stage' + g].clinical }
function sentences(section) { return C.explanations.filter((s) => !section || s.section === section) }
function sentence(id) { return C.explanations.find((s) => s.id === id) }

function overlaySvg({ highlight = SELECTED, quadrants = true, dark = false } = {}) {
  const L = F.landmarks, [ox, oy] = L.axis.origin, len = 2000
  const ln = (v) => `x1="${ox - v[0] * len}" y1="${oy - v[1] * len}" x2="${ox + v[0] * len}" y2="${oy + v[1] * len}"`
  const s = sentence(highlight)
  const regs = !s || !s.refs.lesions ? [] : s.refs.lesions.flatMap((k) => F.lesions[k].regions
    .filter((r) => !s.refs.quadrants || s.refs.quadrants.includes(r.quadrant)).map((r) => ({ ...r, k })))
  const line = dark ? '#ffffff' : '#ffffff'
  return `<svg viewBox="0 0 ${C.image ? 1024 : 1024} ${Math.round(1024 * C.image.height / C.image.width)}" class="absolute inset-0 w-full h-full">
    ${quadrants ? `<line ${ln(L.axis.nasal)} stroke="${line}" stroke-opacity=".5" stroke-width="1.5" stroke-dasharray="6 6"/>
    <line ${ln(L.axis.superior)} stroke="${line}" stroke-opacity=".5" stroke-width="1.5" stroke-dasharray="6 6"/>` : ''}
    <circle cx="${L.optic_disc.x}" cy="${L.optic_disc.y}" r="${L.optic_disc.radius_px}" fill="none" stroke="#fff" stroke-width="2"/>
    <circle cx="${L.fovea.x}" cy="${L.fovea.y}" r="${L.disc_diameter_px}" fill="none" stroke="#00C8FF" stroke-width="2.5" stroke-dasharray="6 4"/>
    <circle cx="${L.fovea.x}" cy="${L.fovea.y}" r="4" fill="#00C8FF"/>
    ${regs.map((r) => `<circle cx="${r.x}" cy="${r.y}" r="${Math.max(9, Math.sqrt(r.area_px / Math.PI) + 6)}" fill="none" stroke="${LESION_COLOR[r.k]}" stroke-width="3"/>`).join('')}
  </svg>`
}

function imageStack(extraClass = '', opts = {}) {
  const shown = sentence(opts.highlight ?? SELECTED)?.refs.lesions ?? LESIONS
  return `<div class="relative ${extraClass}">
    <img src="data/base.jpg" class="block w-full h-auto" alt="Fundus photograph (IDRiD dev-train ${C.source.image_id})">
    ${LESIONS.filter((k) => shown.includes(k)).map((k) => `<img src="data/${k}.png" class="absolute inset-0 w-full h-full" style="opacity:.9" alt="">`).join('')}
    ${overlaySvg(opts)}
  </div>`
}

const ICON = (name, cls = 'w-4 h-4') => `<i data-lucide="${name}" class="${cls}"></i>`
const SECTION_TITLE = { summary: ['Result', 'Summary'], evidence: ['What we found', 'Lesion evidence'], reasoning: ['Why this stage', 'Grade reasoning'],
  macula: ['Centre of vision', 'Macula'], flags: ['Warnings', 'Flags'], limits: ['What this tool cannot check', 'Limits'] }
const SECTION_ICON = { summary: 'clipboard-check', evidence: 'scan-search', reasoning: 'scale', macula: 'crosshair', flags: 'triangle-alert', limits: 'info' }
