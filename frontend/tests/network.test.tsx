import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync, readdirSync } from 'node:fs'
import { renderToStaticMarkup } from 'react-dom/server'
import { canonical, href, parse } from '../src/app/router'
import { ApiError, AUTH_EVENT, api } from '../src/app/api'
import { queueFromTab } from '../src/app/format'
import { ScreeningStatus } from '../src/network/screens/Register'
import { parseNet } from '../src/network/netRouter'
import { en, hi } from '../src/network/i18n/strings'
import { I18nProvider } from '../src/network/i18n/I18n'
import { VerificationBadge, StateBadge, Btn, TextField, Notice, PinField } from '../src/network/components/ui'
import { CampCard } from '../src/network/components/CampCard'
import { SaathiOrb } from '../src/network/components/SaathiOrb'
import { TopicArt } from '../src/network/components/art'
import { net, NetError, type Camp } from '../src/network/api'

const wrap = (el: React.ReactElement) => renderToStaticMarkup(<I18nProvider>{el}</I18nProvider>)
const camp: Camp = {
  id: 7, title: { hi: 'ग्राम नेत्र शिविर (नमूना)', en: 'Village Eye Camp (demo)' }, starts_at: '2026-11-07T10:00:00+05:30', ends_at: '2026-11-07T16:00:00+05:30',
  place: { label: 'Hall', village: 'Demo Village', district: 'Indore', state: 'MP', pin: '453331' }, organiser: { name: 'Demo Trust (simulated)', kind: 'ngo', verification: 'simulated' },
  verification: 'simulated', is_demo: true, state: 'open', planned_capacity: 80, price: null, contact: null, publish_state: 'published', match: 'exact',
}

test('One platform: "/" is the patient home, /specialists the professional entry, /app the workspace', () => {
  assert.equal(parse('/').name, 'network'); assert.equal(parse('/network').name, 'network'); assert.equal(parse('/network/camps/3/register', '?pin=1').name, 'network')
  assert.equal(parse('/specialists').name, 'specialists'); assert.equal(parse('/technology').name, 'specialists')
  assert.equal(parse('/app/worklist').name, 'worklist'); assert.equal(parse('/networkx').name, 'notFound'); assert.equal(parse('/specialistsx').name, 'notFound')
  assert.equal(href('/network/camps'), '/network/camps'); assert.equal(href('/worklist'), '/app/worklist'); assert.equal(href('/'), '/')
  assert.equal(href('/specialists'), '/specialists'); assert.equal(href('/network?x=1'), '/network?x=1')
})

test('Old addresses are redirected once, never in a loop', () => {
  assert.equal(canonical('/network'), '/'); assert.equal(canonical('/network/'), '/'); assert.equal(canonical('/technology'), '/specialists')
  assert.equal(canonical('/cases/RS-1'), '/app/cases/RS-1'); assert.equal(canonical('/worklist'), '/app/worklist')
  for (const p of ['/', '/specialists', '/app/worklist', '/network/camps', '/network/saathi', '/app/cases/RS-1']) assert.equal(canonical(p), null, p)
  for (const p of ['/network', '/technology', '/cases/X']) { const once = canonical(p)!; assert.equal(canonical(once), null, `${p} -> ${once} redirects again`) }
})

test('Network route table', () => {
  assert.deepEqual(parseNet('/'), { name: 'home' })
  assert.deepEqual(parseNet('/network'), { name: 'home' })
  assert.deepEqual(parseNet('/network/camps', '?pin=453331&q=Indore'), { name: 'camps', pin: '453331', q: 'Indore' })
  assert.deepEqual(parseNet('/network/camps/12'), { name: 'camp', id: 12 })
  assert.deepEqual(parseNet('/network/camps/12/register', '?pin=453331&via=saathi'), { name: 'register', id: 12, pin: '453331', viaSaathi: true })
  assert.deepEqual(parseNet('/network/learn/why-screening'), { name: 'topic', slug: 'why-screening' })
  assert.deepEqual(parseNet('/network/organiser/camps/new'), { name: 'organiserCamp', id: 'new' })
  assert.deepEqual(parseNet('/network/status', '?ref=DQN-ABC&code=XXXX-XXXX'), { name: 'status', ref: 'DQN-ABC', code: 'XXXX-XXXX' })
  assert.equal(parseNet('/network/nope').name, 'notFound'); assert.equal(parseNet('/network/camps/abc').name, 'notFound'); assert.equal(parseNet('/network/').name, 'home')
})

test('Hindi covers every English key, keeps placeholders, and is really Devanagari', () => {
  const keys = Object.keys(en) as (keyof typeof en)[]
  const slots = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join()
  const mixedOK = new Set(['home.chip', 'foot.ai', 'nav.brandHome'])
  for (const k of keys) {
    assert.ok(hi[k] && hi[k].trim().length > 0, `missing Hindi for ${k}`)
    assert.equal(slots(hi[k]), slots(en[k]), `placeholders differ for ${k}`)
    if (!mixedOK.has(k) && !k.startsWith('err.csrf') && !/^(about\.r\d+)$/.test(k) && en[k].length > 25) assert.match(hi[k], /[ऀ-ॿ]/, `${k} is not Hindi`)
  }
  assert.equal(Object.keys(hi).length, keys.length)
})

test('the palette meets WCAG AA contrast for the pairs it is used in', () => {
  const css = readFileSync(new URL('../src/network/network.css', import.meta.url), 'utf8')
  const v = (n: string) => css.match(new RegExp(`--${n}:\\s*(#[0-9A-Fa-f]{6})`))![1]
  const lum = (hex: string) => { const c = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(x => (x <= .03928 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4)); return .2126 * c[0] + .7152 * c[1] + .0722 * c[2] }
  const ratio = (a: string, b: string) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + .05) / (y + .05) }
  const pairs: [string, string, string][] = [['ink', 'bg', 'body'], ['ink2', 'bg', 'secondary text'], ['brand', 'bg', 'links'], ['card', 'brand', 'primary button'], ['sage-ink', 'sage-bg', 'verified badge'],
    ['saffron-ink', 'saffron-bg', 'warning'], ['saffron-ink', 'bg', 'eyebrow'], ['danger', 'danger-bg', 'error'], ['brand-deep', 'brand-soft', 'info'], ['ink', 'saffron', 'saffron button'], ['ink2', 'card', 'muted on card']]
  for (const [fg, bg, what] of pairs) {
    const f = fg === 'card' ? v('card') : v(fg), b = v(bg)
    assert.ok(ratio(f, b) >= 4.5, `${what}: ${fg} on ${bg} is ${ratio(f, b).toFixed(2)}`)
  }
})

test('motion is switched off for reduced-motion users and forced colours are handled', () => {
  const css = readFileSync(new URL('../src/network/network.css', import.meta.url), 'utf8')
  assert.match(css, /prefers-reduced-motion: no-preference/); assert.match(css, /forced-colors: active/)
  const anim = css.split('\n').filter(l => /animation:/.test(l) && !/animation: none/.test(l))
  for (const line of anim) {
    const at = css.indexOf(line)
    const before = css.slice(0, at)
    const lastNo = before.lastIndexOf('@media (prefers-reduced-motion: no-preference)'), lastClose = before.lastIndexOf('\n}\n')
    const insideBlock = lastNo > lastClose
    const ownBlock = /@media \(prefers-reduced-motion: no-preference\)/.test(line)
    assert.ok(insideBlock || ownBlock || /nw-spin|nw-turn/.test(line), `unguarded animation: ${line.trim().slice(0, 80)}`)
  }
})

test('status is never colour only: every badge carries text', () => {
  for (const v of ['verified', 'unverified', 'simulated'] as const) {
    const html = wrap(<VerificationBadge v={v} />)
    assert.match(html, new RegExp(`nw-badge ${v}`)); assert.match(html, /<svg/); assert.match(html, new RegExp(en[`badge.${v}`]))
  }
  for (const s of ['open', 'full', 'closed', 'expired', 'cancelled'] as const) assert.match(wrap(<StateBadge s={s} />), new RegExp(en[`state.${s}`]))
})

test('camp card labels demonstration camps and links to details and registration', () => {
  const html = wrap(<CampCard camp={camp} />)
  assert.match(html, /nw-demo-ribbon/); assert.match(html, /Demonstration/); assert.match(html, /href="\/network\/camps\/7"/); assert.match(html, /href="\/network\/camps\/7\/register"/)
  const closed = wrap(<CampCard camp={{ ...camp, state: 'closed' }} />)
  assert.doesNotMatch(closed, /\/register"/)
})

test('form controls are labelled, describe their errors, and stay touch sized', () => {
  const html = wrap(<TextField label="Name" error="Please enter a name." hint="Any name" />)
  assert.match(html, /<label for="[^"]+">Name/); assert.match(html, /aria-invalid="true"/); assert.match(html, /aria-describedby="[^"]+"/); assert.match(html, /role="alert"/)
  assert.match(wrap(<PinField label="PIN" value="45" onChange={() => {}} />), /inputMode="numeric"/)
  const css = readFileSync(new URL('../src/network/network.css', import.meta.url), 'utf8')
  assert.match(css, /\.nw-btn \{[^}]*min-height: 56px/); assert.match(css, /\.nw-input \{[^}]*min-height: 60px/)
  assert.match(wrap(<Notice tone="danger" title="x">y</Notice>), /role="alert"/)
  assert.match(wrap(<Btn to="/network/camps">Go</Btn>), /<a class="nw-btn primary" href="\/network\/camps">/)
})

test('Saathi orb exposes its state to assistive tech and hides purely decorative parts', () => {
  const b = renderToStaticMarkup(<SaathiOrb state="listening" label="Stop listening" />)
  assert.match(b, /aria-label="Stop listening"/); assert.match(b, /data-state="listening"/); assert.match(b, /type="button"/)
  assert.match(renderToStaticMarkup(<SaathiOrb as="div" state="idle" />), /aria-hidden="true"/)
  assert.match(renderToStaticMarkup(<TopicArt slug="why-screening" />), /aria-hidden="true"/)
})

test('API client: CSRF header on every call, structured errors, network failures', async () => {
  const calls: { url: string; init: RequestInit }[] = []
  const g = globalThis as unknown as { fetch: typeof fetch; window: unknown }
  g.window = { setTimeout, clearTimeout }
  g.fetch = (async (url: string, init: RequestInit) => {
    calls.push({ url, init })
    if (url.includes('/registrations') && init.method === 'POST') return new Response(JSON.stringify({ detail: { code: 'camp_closed', message: 'closed' } }), { status: 409 })
    if (url.includes('/camps?pin=12')) return new Response(JSON.stringify({ detail: [{ loc: ['query', 'pin'], msg: 'bad' }] }), { status: 422 })
    if (url.includes('/offline')) throw new TypeError('network down')
    return new Response(JSON.stringify({ items: [], exact: 0, nearby: 0, query: {} }), { status: 200 })
  }) as typeof fetch
  await net.camps({ pin: '453331' })
  assert.equal(calls[0].url, '/api/network/camps?pin=453331'); assert.equal((calls[0].init.headers as Record<string, string>)['X-Requested-With'], 'dqn')
  await assert.rejects(net.register({ camp_id: 1, name: 'A', pin: '453331', language: 'hi', consent: true, contact_consent: false, idempotency_key: 'k' }), (e: unknown) => e instanceof NetError && e.code === 'camp_closed' && e.status === 409)
  assert.equal(calls[1].init.method, 'POST'); assert.equal((calls[1].init.headers as Record<string, string>)['Content-Type'], 'application/json')
  await assert.rejects(net.camps({ pin: '12' }), (e: unknown) => e instanceof NetError && e.code === 'invalid_input')
  g.fetch = (async () => { throw new TypeError('down') }) as typeof fetch
  await assert.rejects(net.me(), (e: unknown) => e instanceof NetError && e.code === 'network')
})

test('no secret or provider key ever appears in the Network frontend source', () => {
  const walk = (d: URL): string[] => readdirSync(d, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(new URL(`${e.name}/`, d)) : [new URL(e.name, d).pathname])
  for (const f of walk(new URL('../src/network/', import.meta.url)).filter(f => /\.(ts|tsx)$/.test(f))) {
    const src = readFileSync(decodeURIComponent(f).replace(/^\/([A-Za-z]:)/, '$1'), 'utf8')
    assert.doesNotMatch(src, /GEMINI_API_KEY|generativelanguage\.googleapis|AIza[0-9A-Za-z_-]{20,}/, f)
  }
})

test('Specialist sign-in route and queue names (old ?tab links keep working)', () => {
  assert.deepEqual(parse('/app/login', '?next=/cases/RS-1'), { name: 'login', next: '/cases/RS-1' })
  assert.equal(queueFromTab('review'), 'attention'); assert.equal(queueFromTab('reviewed'), 'signed'); assert.equal(queueFromTab('signed'), 'signed')
  assert.equal(queueFromTab(null), 'attention'); assert.equal(queueFromTab('bogus'), 'attention')
})

test('clinical API: 401 raises ApiError with the server code and asks the app to show sign-in', async () => {
  const g = globalThis as unknown as Record<string, unknown>
  const original = globalThis.fetch, hadWindow = 'window' in g, oldWindow = g.window
  const events: string[] = []
  g.window = { dispatchEvent: (e: Event) => { events.push(e.type); return true } }
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: { code: 'session_expired', message: 'Expired' } }), { status: 401, headers: { 'content-type': 'application/json' } })
  try {
    await assert.rejects(api.cases(), (e: unknown) => e instanceof ApiError && e.status === 401 && e.code === 'session_expired' && e.message === 'Expired')
    assert.deepEqual(events, [AUTH_EVENT])
  } finally {
    globalThis.fetch = original
    if (hadWindow) g.window = oldWindow; else delete g.window
  }
})

test('patient screening status shows only approved wording: no stage, image or clinical detail', () => {
  const urgent = wrap(<ScreeningStatus s={{ state: 'decision_recorded', next_action: 'urgent_referral', missing_eyes: ['left'], eyes_awaiting_review: 0, decided_at: '2026-11-01T10:00:00+05:30' }} />)
  assert.ok(urgent.includes(en['next.urgent_referral']))                            // the fixed wording (English when no language is chosen)
  assert.match(urgent, /urgent/)                                                   // urgent styling
  assert.doesNotMatch(urgent, /stage|Stage|चरण|grade|RS-\d|<img/)
  const incomplete = wrap(<ScreeningStatus s={{ state: 'incomplete', next_action: null, missing_eyes: ['right', 'left'], quality_provisional: true }} />)
  assert.ok(incomplete.includes(en['scr.incomplete']) && incomplete.includes('right eye and left eye'))
  for (const k of ['scr.not_linked', 'scr.in_progress', 'scr.quality_check', 'scr.awaiting_review', 'scr.decision_recorded', 'scr.unavailable',
    'next.urgent_referral', 'next.referral', 'next.examination', 'next.recapture', 'next.follow_up', 'next.routine_rescreen'] as const) {
    assert.ok(en[k] && hi[k], k)
  }
})
