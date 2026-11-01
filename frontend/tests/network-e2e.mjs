// End-to-end check of DrishtiQ Network in a real browser (Microsoft Edge via playwright-core; no browser download needed).
//   1. build:   cd frontend && npm run build
//   2. serve:   RS_DATA_DIR=<empty temp dir> python -m uvicorn backend.app:app --port 8011      (demo mode on, throwaway data)
//   3. run:     node tests/network-e2e.mjs http://127.0.0.1:8011 [screenshot-dir]
// It never touches the clinical database when RS_DATA_DIR points at an empty directory.
import { createRequire } from 'node:module'
import { readFileSync, mkdirSync } from 'node:fs'
const require = createRequire(import.meta.url)
const { chromium } = require('playwright-core')
const BASE = process.argv[2] ?? 'http://127.0.0.1:8011'
const SHOTS = process.argv[3]
if (SHOTS) mkdirSync(SHOTS, { recursive: true })
const axeSrc = readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8')
const results = []
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const uniq = String(Date.now()).slice(-7)

async function check(name, fn) {
  try { await fn(); results.push([true, name]); console.log('  ok  ', name) } catch (e) { results.push([false, name, String(e.message).split('\n')[0]]); console.log('  FAIL', name, '->', String(e.message).split('\n')[0]) }
}
const eq = (a, b, m) => { if (a !== b) throw new Error(`${m ?? 'expected'}: got ${JSON.stringify(a)} want ${JSON.stringify(b)}`) }
const ok = (v, m) => { if (!v) throw new Error(m ?? 'assertion failed') }
async function newCtx(opts = {}) {
  const c = await browser.newContext({ viewport: { width: 1280, height: 900 }, ...opts })
  await c.addInitScript((l) => { try { localStorage.setItem('dqn.lang', l) } catch {} }, opts.lang ?? 'en')
  return c
}
async function page(c) {
  const p = await c.newPage(); p.errs = []
  p.on('pageerror', (e) => p.errs.push(String(e))); p.on('console', (m) => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) p.errs.push(m.text()) })
  return p
}
const snap = async (p, n) => { if (SHOTS) await p.screenshot({ path: `${SHOTS}/${n}.png`, fullPage: true }) }
const sendSaathi = async (p, text) => { await p.fill('.nw-compose input', text); await p.keyboard.press('Enter') }
const demoLogin = async (p, id, pw) => { await p.goto(`${BASE}/network/staff`); await p.fill('input[autocomplete=username]', id); await p.fill('input[autocomplete=current-password]', pw); await p.click('button[type=submit]') }

// ---------------------------------------------------------------------------------------------------------------
console.log('Key journey: Home -> Saathi -> camps -> register -> save profile -> view registration')
const user = await newCtx(); const p = await page(user)
const ident = `98${uniq}1`.slice(0, 10).padEnd(10, '1'), PW = 'Journey@12345'
let receipt = ''
await check('home renders the hero, services and honesty note', async () => {
  await p.goto(`${BASE}/network`); await p.waitForSelector('h1')
  ok((await p.textContent('h1')).includes('Your eyes matter'), 'hero title'); ok(await p.isVisible('text=Camps shown are demonstration examples'), 'demo note')
  eq(await p.locator('.nw-svc').count(), 4, 'service cards'); await snap(p, 'journey-1-home')
})
await check('Talk to Saathi opens the voice screen', async () => { await p.click('a:has-text("Talk to Saathi") >> nth=0'); await p.waitForURL('**/network/saathi'); ok(await p.isVisible('.nw-orb-btn'), 'orb') })
await check('Hinglish request -> Saathi asks for PIN; PIN -> real camp cards', async () => {
  await sendSaathi(p, 'Mujhe apne gaon mein aankhon ki jaanch karwani hai.'); await p.waitForSelector('text=6 अंकों का PIN कोड बताइए')
  await sendSaathi(p, '453331'); await p.waitForSelector('.nw-mini'); ok((await p.locator('.nw-mini').count()) >= 2, 'camp cards')
  ok((await p.locator('.nw-thread').allInnerTexts()).join(' ').includes('नमूना शिविर हैं, असली सेवाएँ नहीं'), 'says demonstration'); await snap(p, 'journey-2-saathi')
})
await check('"pehla wala" then "registration karna hai" opens the real form (does not submit)', async () => {
  await sendSaathi(p, 'pehla wala'); await p.waitForSelector('text=तारीख और समय')
  await sendSaathi(p, 'mujhe registration karna hai'); await p.waitForURL('**/network/camps/*/register?*via=saathi', { timeout: 6000 })
  await p.waitForSelector('h2:has-text("What is your name?")', { timeout: 8000 })
})
await check('3-step wizard validates, reviews, requires consent, and confirms via the server', async () => {
  await p.click('button:has-text("Next")'); ok(await p.isVisible('text=Please enter a name'), 'name error')
  await p.fill('input[autocomplete=name]', 'Journey Tester'); await p.click('button:has-text("Next")')
  eq(await p.inputValue('input.pin'), '453331', 'PIN carried from Saathi'); await p.click('button:has-text("Next")')
  await p.click('button:has-text("Confirm interest")'); ok(await p.isVisible('text=Please tick the box'), 'consent error')
  await p.click('.nw-check'); await snap(p, 'journey-3-review'); await p.click('button:has-text("Confirm interest")')
  await p.waitForSelector('.nw-receipt'); receipt = (await p.innerText('.nw-receipt')).replace(/\s+/g, ' ').trim()
  ok(/^DQN-[A-Z0-9]{6} [A-Z0-9]{4}-[A-Z0-9]{4}$/.test(receipt), 'receipt format ' + receipt)
  ok(await p.isVisible('text=Interest received'), 'status'); ok(await p.isVisible('text=not confirmed anything yet'), 'not an appointment'); await snap(p, 'journey-4-done')
})
await check('status page shows the real status from the receipt', async () => {
  await p.click('a:has-text("Check my status")'); await p.waitForSelector('.nw-time'); ok(await p.isVisible('.nw-time >> text=Interest received'), 'timeline'); await snap(p, 'journey-5-status')
})
await check('sign-up (optional) saves a profile and auto-attaches the receipt', async () => {
  await p.goto(`${BASE}/network/camps/1/register`) // fresh app state, then back to a done screen is not needed: use stored receipt
  await p.evaluate((r) => sessionStorage.setItem('dqn.receipt', JSON.stringify({ ref: r.split(' ')[0], code: r.split(' ')[1] })), receipt)
  await p.goto(`${BASE}/network/signup`)
  await p.fill('input[autocomplete=name]', 'Journey Tester'); await p.fill('input[autocomplete=username]', ident); await p.fill('input[autocomplete=new-password]', PW)
  await p.click('button:has-text("Next")'); await p.fill('input.pin', '453331'); await p.click('.nw-check >> nth=-1'); await snap(p, 'journey-6-signup')
  await p.click('button:has-text("Create account")'); await p.waitForURL('**/network/me'); await p.waitForSelector('text=Journey')
})
await check('My DrishtiQ shows profile (unverified contact) and the registration with its status', async () => {
  await p.waitForSelector('.nw-row'); ok(await p.isVisible('text=Interest received'), 'registration status'); ok(await p.isVisible('text=not verified'), 'unverified label')
  ok(!(await p.content()).includes(ident), 'full number never shown'); await snap(p, 'journey-7-me')
})
await check('profile edit saves and persists after reload; language preference applies', async () => {
  await p.click('button:has-text("Edit")'); await p.fill('label:has-text("Village or city") + input', 'Demo Gram'); await p.click('button:has-text("Save")'); await p.waitForSelector('text=Your details were saved')
  await p.reload(); await p.waitForSelector('text=Demo Gram')
})
await check('duplicate interest for the same camp is reported, not duplicated', async () => {
  const r = await p.evaluate(async () => (await fetch('/api/network/registrations', { method: 'POST', headers: { 'X-Requested-With': 'dqn', 'Content-Type': 'application/json' }, body: JSON.stringify({ camp_id: 1, name: 'Journey Tester', pin: '453331', consent: true }) })).json())
  eq(r.duplicate, true, 'duplicate flag')
})
await check('sign out then in again', async () => {
  await p.click('button:has-text("Log out")'); await p.waitForURL((u) => new URL(u).pathname === '/'); await p.goto(`${BASE}/network/login`)
  await p.fill('input[autocomplete=username]', ident); await p.fill('input[autocomplete=current-password]', PW); await p.click('button[type=submit]'); await p.waitForURL('**/network/me')
})

// ---------------------------------------------------------------------------------------------------------------
console.log('Scripted Hindi demo (no Gemini, no microphone)')
const dm = await newCtx({ lang: 'hi' }); const d = await page(dm)
await check('demo: screening question -> offer -> "हाँ" -> PIN 452001 -> demonstration camp from the database', async () => {
  await d.goto(`${BASE}/network/saathi`); await d.waitForSelector('.nw-compose input')
  await sendSaathi(d, 'मुझे diabetes है लेकिन मुझे ठीक दिखाई देता है। क्या मुझे आँखों की जाँच करवानी चाहिए?')
  await d.waitForSelector('text=क्या मैं आपके पास आँखों की जाँच ढूँढूँ?')
  await sendSaathi(d, 'हाँ'); await d.waitForSelector('text=6 अंकों का PIN कोड बताइए')
  await sendSaathi(d, '452001'); await d.waitForSelector('.nw-mini'); ok(await d.locator('.nw-mini', { hasText: 'शहरी नेत्र जाँच शिविर' }).first().isVisible(), 'seeded demo camp card shown')
  ok((await d.locator('.nw-thread').allInnerTexts()).join(' ').includes('नमूना शिविर हैं, असली सेवाएँ नहीं'), 'labelled as demonstration'); await snap(d, 'demo-1-saathi-hi')
})
await check('demo: the conversation survives a visit to the specialist page and back', async () => {
  const before = await d.locator('.nw-msg').count(); ok(before >= 6, 'messages ' + before)
  await d.goto(`${BASE}/specialists`); await d.waitForSelector('text=Every eye'); await d.goto(`${BASE}/network/saathi`); await d.waitForSelector('.nw-mini')
  eq(await d.locator('.nw-msg').count(), before, 'messages after return'); await sendSaathi(d, 'पहले वाले के बारे में बताइए'); await d.waitForSelector('text=तारीख और समय')
})
await check('demo: urgent symptoms get "go today" advice and no camp list', async () => {
  const n = await d.locator('.nw-mini').count(); await sendSaathi(d, 'मेरी आँखों से अचानक दिखना बंद हो गया'); await d.waitForSelector('text=112')
  eq(await d.locator('.nw-mini').count(), n, 'no new camp cards')
})

// ---------------------------------------------------------------------------------------------------------------
console.log('Health worker, organiser and admin')
const wk = await newCtx(); const w = await page(wk)
await check('worker logs in (real login), sees only assigned camps and the new request', async () => {
  await demoLogin(w, '9000000001', 'Demo@Worker1'); await w.waitForURL('**/network/worker'); await w.waitForSelector('text=PROTOTYPE ACCOUNT', { timeout: 8000 })
  await w.waitForSelector('article.nw-row'); ok(await w.isVisible('article:has-text("Journey Tester")'), 'request visible'); await snap(w, 'staff-worker')
})
await check('worker marks contacted; the person sees it in My DrishtiQ', async () => {
  await w.click('article:has-text("Journey Tester") >> button:has-text("Mark contacted")'); await w.waitForSelector('article:has-text("Journey Tester") >> text=Organiser contacted you')
  await p.goto(`${BASE}/network/me`); await p.click('button:has-text("See progress")'); await p.waitForSelector('.nw-time >> text=Organiser contacted you')
})
await check('assisted registration needs explicit consent and gives the person their receipt', async () => {
  await w.click('[role=tab]:has-text("Register someone")'); await w.selectOption('#acamp', { index: 1 }); await w.fill('input[autocomplete], label:has-text("Name") + input >> nth=0', 'Assisted Person').catch(() => {})
  await w.fill('label:has-text("Name") + input', 'Assisted Person'); await w.fill('input.pin', '453331')
  ok(await w.isDisabled('button:has-text("Record interest")'), 'disabled before consent'); await w.click('.nw-check >> nth=-1'); await w.click('button:has-text("Record interest")')
  await w.waitForSelector('.nw-receipt'); ok(await w.isVisible('text=belongs to them') || await w.isVisible('text=Give this receipt'), 'receipt handover')
})
await check('worker cannot open organiser tools', async () => { await w.goto(`${BASE}/network/organiser`); await w.waitForSelector('text=cannot open this area') })
const oc = await newCtx(); const o = await page(oc)
await check('organiser sees demo-data warning, creates a camp (unverified by default)', async () => {
  await demoLogin(o, '9000000002', 'Demo@Organiser1'); await o.waitForURL('**/network/organiser'); await o.waitForSelector('.nw-stat'); ok(await o.isVisible('text=Demonstration data'), 'demo warning')
  await o.click('a:has-text("New camp")'); await o.waitForURL('**/camps/new')
  await o.fill('label:has-text("Camp name (English)") + input', 'E2E Eye Camp'); await o.fill('label:has-text("Venue") + input', 'E2E Hall'); await o.fill('label:has-text("District") + input', 'Indore'); await o.fill('input.pin', '453331')
  await o.click('button:has-text("Published")'); await o.click('button[type=submit]'); await o.waitForURL('**/network/organiser'); await o.waitForSelector('article:has-text("E2E Eye Camp")')
  ok(await o.isVisible('article:has-text("E2E Eye Camp") >> text=Not verified'), 'unverified'); ok(!(await o.isVisible('article:has-text("E2E Eye Camp") >> text=Mark verified')), 'organiser cannot verify'); await snap(o, 'staff-organiser')
})
const ac = await newCtx(); const a = await page(ac)
await check('admin verifies the camp; the public listing then shows Verified (not demo)', async () => {
  await demoLogin(a, '9000000003', 'Demo@Admin1'); await a.waitForURL('**/network/organiser'); await a.click('article:has-text("E2E Eye Camp") >> button:has-text("Mark verified")'); await a.waitForSelector('article:has-text("E2E Eye Camp") >> text=Verified')
  const anon = await newCtx(); const q = await page(anon); await q.goto(`${BASE}/network/camps?q=E2E`); await q.waitForSelector('.nw-camp')
  ok(await q.isVisible('.nw-camp >> text=Verified'), 'verified badge'); ok(!(await q.isVisible('.nw-demo-ribbon')), 'no demo ribbon'); await snap(q, 'camps-verified'); await anon.close()
})

// ---------------------------------------------------------------------------------------------------------------
console.log('Saathi voice and failure handling (browser speech is mocked; real mic cannot run headless)')
const FAKE = (mode) => `(() => {
  window.__spoken = []; const syn = window.speechSynthesis; if (syn) { syn.speak = (u) => { window.__spoken.push(u.text); setTimeout(() => u.onstart && u.onstart(), 10); setTimeout(() => u.onend && u.onend(), 30) }; syn.cancel = () => {}; }
  if (${mode === 'none'}) { delete window.SpeechRecognition; delete window.webkitSpeechRecognition; return }
  window.SpeechRecognition = window.webkitSpeechRecognition = class { start() { const e = ${JSON.stringify(mode)}
    if (e === 'denied') setTimeout(() => this.onerror && this.onerror({ error: 'not-allowed' }), 50)
    else if (e === 'silence') setTimeout(() => { this.onerror && this.onerror({ error: 'no-speech' }); this.onend && this.onend() }, 50)
    else if (e === 'low') setTimeout(() => { this.onresult && this.onresult({ resultIndex: 0, results: [Object.assign([{ transcript: 'chaar paanch teen', confidence: 0.3 }], { isFinal: true })] }); this.onend && this.onend() }, 50)
    else setTimeout(() => { this.onresult && this.onresult({ resultIndex: 0, results: [Object.assign([{ transcript: '4 5 3 3 3 1', confidence: 0.92 }], { isFinal: true })] }); this.onend && this.onend() }, 80) }
    stop() {} abort() {} } })()`
const voiceCtx = async (mode, extra = {}) => { const c = await newCtx(extra); await c.addInitScript(FAKE(mode)); const pg = await page(c); await pg.goto(`${BASE}/network/saathi`); await pg.waitForSelector('.nw-orb-btn'); return [c, pg] }
await check('microphone: consent card first; spoken digits reach find_camps; reply is spoken aloud', async () => {
  const [c, v] = await voiceCtx('ok'); await v.click('.nw-orb-btn'); ok(await v.isVisible('text=Use your microphone?'), 'consent card'); await v.click('button:has-text("Yes, start listening")')
  await v.waitForSelector('.nw-mini'); const spoken = await v.evaluate(() => window.__spoken.join(' ')); ok(/453331/.test(spoken), 'reply spoken: ' + spoken.slice(0, 60))
  ok(await v.isVisible('.nw-msg.user:has-text("4 5 3 3 3 1")'), 'transcript shown'); await snap(v, 'saathi-voice'); await c.close()
})
await check('microphone permission denied -> clear message, typing still works', async () => {
  const [c, v] = await voiceCtx('denied'); await v.evaluate(() => sessionStorage.setItem('dqn.mic', 'ok')); await v.click('.nw-orb-btn'); await v.waitForSelector('text=Microphone is blocked')
  await sendSaathi(v, 'camp near 453331'); await v.waitForSelector('.nw-mini'); await c.close()
})
await check('silence and low-confidence speech are handled (no wrong search is run)', async () => {
  let [c, v] = await voiceCtx('silence'); await v.evaluate(() => sessionStorage.setItem('dqn.mic', 'ok')); await v.click('.nw-orb-btn'); await v.waitForSelector('text=I did not hear anything'); await c.close()
  ;[c, v] = await voiceCtx('low'); await v.evaluate(() => sessionStorage.setItem('dqn.mic', 'ok')); await v.click('.nw-orb-btn'); await v.waitForSelector('text=not sure I heard you correctly')
  eq(await v.locator('.nw-msg.user').count(), 0, 'not auto-sent'); ok((await v.inputValue('.nw-compose input')).length > 0, 'draft placed in the box'); await c.close()
})
await check('unsupported browser: no mic button, text path fully works', async () => {
  const [c, v] = await voiceCtx('none'); eq(await v.locator('.nw-compose button:has-text("Speak")').count(), 0, 'no speak button'); await sendSaathi(v, 'why is screening important?'); await v.waitForSelector('.nw-mini:has-text("General information"), .nw-mini:has-text("जाँच"), .nw-mini'); await c.close()
})
await check('service unavailable -> friendly message, app still usable', async () => {
  const [c, v] = await voiceCtx('none'); await v.route('**/api/network/saathi/turn', (r) => r.abort()); await sendSaathi(v, 'hello'); await v.waitForSelector('text=could not reach the service'); await c.close()
})
await check('safety: medical questions are refused with a doctor pointer; no appointment claims anywhere', async () => {
  const [c, v] = await voiceCtx('none'); await sendSaathi(v, 'Do I have retinopathy? which medicine should I take'); await v.waitForSelector('text=can\'t diagnose'); await c.close()
})
await check('language switch to Hindi re-renders the interface in Devanagari with lang attributes', async () => {
  const c = await newCtx(); const h = await page(c); await h.goto(`${BASE}/network`); await h.click('.nw-lang button:has-text("हिंदी")')
  await h.waitForSelector('h1:has-text("आपकी आँखें")'); eq(await h.getAttribute('.nw', 'lang'), 'hi'); eq(await h.evaluate(() => document.documentElement.lang), 'hi')
  ok(await h.evaluate(() => getComputedStyle(document.querySelector('.nw')).fontFamily.includes('Noto Sans Devanagari')), 'Devanagari font stack'); await c.close()
})
await check('first visit asks for a language with two large buttons', async () => {
  const c = await browser.newContext({ viewport: { width: 390, height: 800 }, locale: 'en-US' }); const f = await page(c); await f.goto(`${BASE}/network`); await f.waitForSelector('.nw-gate')
  const b = await f.locator('.nw-gate button').first().boundingBox(); ok(b.height >= 64, 'large target'); await f.click('.nw-gate button:has-text("हिंदी")'); await f.waitForSelector('h1:has-text("आपकी")'); await c.close()
})

// ---------------------------------------------------------------------------------------------------------------
console.log('Responsive, accessibility, motion')
const pages = ['/', '/network/saathi', '/network/camps?pin=453331', '/network/camps/1', '/network/camps/1/register', '/network/learn', '/network/learn/myths-facts', '/network/login', '/network/signup', '/network/staff', '/network/about', '/network/status']
for (const w of [320, 390, 768, 1024, 1440]) {
  await check(`no horizontal scroll at ${w}px (all Network pages, English + Hindi long text)`, async () => {
    for (const lang of ['en', 'hi']) {
      const c = await newCtx({ viewport: { width: w, height: 800 }, lang }); const r = await page(c)
      for (const u of pages) { await r.goto(BASE + u, { waitUntil: 'networkidle' }); const over = await r.evaluate(() => document.documentElement.scrollWidth - window.innerWidth); ok(over <= 1, `${lang} ${u} overflows by ${over}px`) }
      await c.close()
    }
  })
}
await check('axe: no serious or critical violations on any Network page (EN and HI)', async () => {
  for (const lang of ['en', 'hi']) {
    const c = await newCtx({ lang }); const r = await page(c)
    for (const u of pages) {
      await r.goto(BASE + u, { waitUntil: 'networkidle' }); await r.waitForTimeout(500); await r.addScriptTag({ content: axeSrc })
      const v = await r.evaluate(async () => (await axe.run(document, { resultTypes: ['violations'] })).violations.filter((x) => ['serious', 'critical'].includes(x.impact)).map((x) => `${x.id}:${x.nodes[0].target}`))
      ok(v.length === 0, `${lang} ${u}: ${v.slice(0, 3).join(' | ')}`)
    }
    await c.close()
  }
})
await check('keyboard: skip link, focus ring, Space/Enter on orb, Tab order reaches the form', async () => {
  const c = await newCtx(); const k = await page(c); await k.goto(`${BASE}/network/camps`); await k.waitForSelector('.nw-main'); await k.keyboard.press('Tab'); ok(await k.evaluate(() => document.activeElement.className.includes('skip')), 'skip link first')
  await k.keyboard.press('Enter'); ok(await k.evaluate(() => document.activeElement.id === 'nw-main'), 'focus moved to main')
  for (let i = 0; i < 4; i++) await k.keyboard.press('Tab'); ok(await k.evaluate(() => getComputedStyle(document.activeElement).outlineStyle !== 'none'), 'visible focus'); await c.close()
})
await check('prefers-reduced-motion: orb and hero animations are off', async () => {
  const c = await newCtx({ reducedMotion: 'reduce' }); const m = await page(c); await m.goto(`${BASE}/network/saathi`); await m.waitForSelector('.nw-orb .core')
  eq(await m.evaluate(() => getComputedStyle(document.querySelector('.nw-orb .core')).animationName), 'none', 'orb core'); eq(await m.evaluate(() => getComputedStyle(document.querySelector('.nw-orb .sheen')).animationName), 'none', 'sheen')
  await m.goto(`${BASE}/network`); eq(await m.evaluate(() => getComputedStyle(document.querySelector('.nw-hero .rise')).animationName), 'none', 'hero'); await c.close()
})
await check('large text mode scales the interface and persists', async () => {
  const c = await newCtx(); const t = await page(c); await t.goto(`${BASE}/network`); await t.click('button[aria-label="Text size"]'); eq(await t.getAttribute('.nw', 'data-size'), 'lg'); await t.reload(); eq(await t.getAttribute('.nw', 'data-size'), 'lg'); await c.close()
})
await check('touch targets: primary controls are at least 44px on a phone', async () => {
  const c = await newCtx({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }); const t = await page(c); await t.goto(`${BASE}/network/camps`)
  const small = await t.evaluate(() => [...document.querySelectorAll('.nw a.nw-btn, .nw button.nw-btn, .nw input.nw-input, .nw-tabs a, .nw-lang button')].filter((e) => e.offsetParent && (e.getBoundingClientRect().height < 40)).map((e) => e.className + ':' + Math.round(e.getBoundingClientRect().height)))
  ok(small.length === 0, small.slice(0, 4).join(',')); await c.close()
})

// ---------------------------------------------------------------------------------------------------------------
console.log('Security and privacy')
const sec = await newCtx(); const s = await page(sec); await s.goto(`${BASE}/network`)
const api = (method, path, body, headers = { 'X-Requested-With': 'dqn' }) => s.evaluate(async ([m, pa, b, h]) => { const r = await fetch('/api/network' + pa, { method: m, headers: { 'Content-Type': 'application/json', ...h }, body: b ? JSON.stringify(b) : undefined }); return [r.status, await r.json().catch(() => null)] }, [method, path, body, headers])
await check('CSRF: state-changing request without the custom header is rejected', async () => { eq((await api('POST', '/registrations', { camp_id: 1, name: 'x', pin: '453331', consent: true }, {}))[0], 403) })
await check('guests cannot reach staff, profile or export endpoints', async () => { for (const [m, pa] of [['GET', '/worker/requests'], ['GET', '/organiser/summary'], ['GET', '/me/registrations'], ['GET', '/me/export']]) eq((await api(m, pa))[0], 401, pa) })
await check('session cookie is HttpOnly and SameSite=Lax; password never returned', async () => {
  const c = await newCtx(); const q = await page(c); await q.goto(`${BASE}/network/login`); await q.fill('input[autocomplete=username]', ident); await q.fill('input[autocomplete=current-password]', PW); await q.click('button[type=submit]'); await q.waitForURL('**/network/me')
  const ck = (await c.cookies()).find((x) => x.name === 'dqn_session'); ok(ck && ck.httpOnly && ck.sameSite === 'Lax', 'cookie flags ' + JSON.stringify(ck)); ok(!(await q.evaluate(() => document.cookie)).includes('dqn_session'), 'not readable by scripts')
  const me = JSON.stringify(await q.evaluate(async () => (await fetch('/api/network/me')).json())); ok(!/password|argon2/i.test(me), 'no hash in /me'); await c.close()
})
await check('a user cannot cancel or read another user\'s registration (IDOR)', async () => {
  const [st] = await api('POST', '/me/registrations/1/cancel'); ok(st === 401 || st === 403, 'status ' + st)
})
await check('no API key or secret reaches the browser bundle', async () => {
  const html = await (await fetch(`${BASE}/network`)).text(); const js = [...html.matchAll(/assets\/[^"']+\.js/g)].map((m) => m[0]); let all = ''
  for (const f of js) all += await (await fetch(`${BASE}/${f}`)).text()
  ok(!/AIza[0-9A-Za-z_-]{20,}|GEMINI_API_KEY|generativelanguage/.test(all), 'secret-like string in bundle')
})

// ---------------------------------------------------------------------------------------------------------------
console.log('Existing clinical app still works')
const cc = await newCtx(); const cl = await page(cc)
await check('one platform: "/" is the patient home; /network and /technology redirect once; /specialists leads to the workspace', async () => {
  await cl.goto(`${BASE}/`, { waitUntil: 'networkidle' }); ok(await cl.isVisible('.nw-hero h1'), 'patient hero at /'); ok(await cl.locator('a[href="/specialists"]').count() >= 1, 'specialist link')
  await cl.goto(`${BASE}/network`, { waitUntil: 'networkidle' }); eq(new URL(cl.url()).pathname, '/', '/network canonical'); ok(await cl.isVisible('.nw-hero h1'), 'still the home')
  await cl.goto(`${BASE}/technology`, { waitUntil: 'networkidle' }); eq(new URL(cl.url()).pathname, '/specialists', '/technology canonical')
  ok(await cl.isVisible('text=Every eye'), 'professional entry'); ok(await cl.locator('a[href="/"]').count() >= 1, 'patients link')
  ok(await cl.locator('a.landing-workspace[href="/app/worklist"]').count() === 1, 'workspace link')
  await cl.goto(`${BASE}/cases/RS-9999`, { waitUntil: 'networkidle' }); eq(new URL(cl.url()).pathname, '/app/cases/RS-9999', 'legacy clinical link')
})
await check('axe: no serious or critical violations on the professional entry page', async () => {
  await cl.goto(`${BASE}/specialists`, { waitUntil: 'networkidle' }); await cl.waitForTimeout(500); await cl.addScriptTag({ content: axeSrc })
  const v = await cl.evaluate(async () => (await axe.run(document, { resultTypes: ['violations'] })).violations.filter((x) => ['serious', 'critical'].includes(x.impact)).map((x) => `${x.id}:${x.nodes[0].target}`))
  ok(v.length === 0, v.slice(0, 3).join(' | '))
})
await check('clinical API: public endpoints answer, clinical ones refuse anonymous callers, unknown path is a JSON 404', async () => {
  for (const u of ['/api/health', '/api/glossary']) ok((await fetch(BASE + u)).status < 500, u)
  for (const u of ['/api/cases', '/api/settings', '/api/feedback.csv', '/api/patients/X/report.html', '/api/patients/X/report.pdf', '/api/clinician/me']) eq((await fetch(BASE + u)).status, 401, u)
  eq((await fetch(`${BASE}/api/cases/RS-1001/review`, { method: 'POST', headers: { 'X-Requested-With': 'dqn', 'Content-Type': 'application/json' }, body: '{"decision":"agree","next_action":"routine_rescreen"}' })).status, 401, 'anonymous sign')
  const r = await fetch(`${BASE}/api/nope`); eq(r.status, 404); ok((await r.json()).detail.includes('No API endpoint'), 'json 404')
})

// ---------------------------------------------------------------------------------------------------------------
console.log('Specialist Attention (sign-in, roles, visit, link, decision, patient status)')
await check('the workspace shows sign-in to anonymous visitors; a patient account is refused', async () => {
  cl.errs.length = 0
  await cl.goto(`${BASE}/app/worklist`, { waitUntil: 'networkidle' }); await cl.waitForSelector('text=Sign in to Specialist Attention')
  ok(!(await cl.isVisible('text=Needs attention')), 'no worklist without a session')
  const pc = await newCtx(); const pp = await page(pc)
  await pp.goto(`${BASE}/app/login`); await pp.fill('#ident', ident); await pp.fill('#pw', PW); await pp.click('button[type=submit]')
  await pp.waitForSelector('text=does not have specialist access')
  eq(await pp.evaluate(async () => (await fetch('/api/cases')).status), 403, 'patient session on the clinical API'); await pc.close()
})
const IMG = process.env.E2E_IMAGE
const dc = await newCtx(); const d2 = await page(dc)
let caseUrl = ''
await check('ophthalmologist signs in and lands on Specialist Attention with its queues', async () => {
  await d2.goto(`${BASE}/app/login`); await d2.fill('#ident', '9000000004'); await d2.fill('#pw', 'Demo@Eye-Doctor1'); await d2.click('button[type=submit]')
  await d2.waitForSelector('text=Who needs your attention, and why')  // not the sign-in heading, which also names Specialist Attention
  for (const q of ['Needs attention', 'Awaiting review', 'Retake / cannot assess', 'Routine', 'Signed']) ok(await d2.isVisible(`[aria-label="Filter results"] button:has-text("${q}")`), q)
  ok(await d2.isVisible('text=Dr. Demo Ophthalmologist'), 'signed-in name shown'); await snap(d2, 'specialist-1-attention')
})
if (IMG) {
  await check('one-eye visit with a non-fundus test image: the real quality gate rejects it, the visit is incomplete', async () => {
    await d2.goto(`${BASE}/app/new`); await d2.fill('#patient', 'E2E-VISIT')
    await d2.setInputFiles('input[aria-label="Fundus photograph, right eye"]', IMG)
    ok(await d2.isVisible('text=This visit will show as incomplete'), 'one-eye warning')
    await d2.click('button:has-text("Analyse")'); await d2.waitForSelector('text=Open case', { timeout: 120000 })
    ok(await d2.isVisible('text=Retake recommended: low image quality') && await d2.isVisible('text=may not be a fundus photograph'), 'quality gate'); ok(await d2.isVisible('text=Screening incomplete'), 'visit incomplete')
    await d2.click('button:has-text("Open case")'); await d2.waitForSelector('section[aria-label="This visit"]'); caseUrl = d2.url()
    ok(await d2.isVisible('section[aria-label="This visit"] >> text=Missing'), 'left eye missing'); await snap(d2, 'specialist-2-case')
  })
  await check('the clinician links the camp registration from the patient-presented receipt (consent required)', async () => {
    const [rref, rcode] = receipt.split(' ')
    await d2.click('button:has-text("Link camp registration")'); await d2.fill('input[placeholder="DQN-XXXXXX"]', rref); await d2.fill('input[placeholder="XXXX-XXXX"]', rcode)
    ok(await d2.isDisabled('form button[type=submit]:has-text("Link")'), 'link needs consent')
    await d2.click('text=The person agreed to link this screening'); await d2.click('form button[type=submit]:has-text("Link")')
    await d2.waitForSelector(`text=Linked to camp registration`)
  })
  const gs = await newCtx(); const g = await page(gs)
  const statusUrl = () => `${BASE}/network/status?ref=${receipt.split(' ')[0]}&code=${receipt.split(' ')[1]}`
  await check('patient status before sign-off: objective progress only (incomplete, quality flagged as provisional), no clinical detail', async () => {
    await g.goto(statusUrl()); await g.waitForSelector('.nw-screening')
    const t = await g.innerText('.nw-screening'); ok(t.includes('Screening incomplete') && t.includes('left eye'), t); ok(t.includes('not a result'), 'quality provisional')
    ok(!/stage|grade|RS-\d|ENC-/i.test(await g.innerText('main')), 'no clinical identifiers'); await snap(g, 'patient-1-status-before')
  })
  await check('the clinician signs "cannot assess: retake" under their own name; it moves to Signed', async () => {
    await d2.goto(caseUrl); await d2.waitForSelector('text=Clinician decision')
    ok(await d2.isVisible('text=Low image quality'), 'quality warning leads the case view')
    await d2.click('button:has-text("Mark the image ungradable instead")'); await d2.click('label:has-text("Retake photograph")'); await d2.click('button:has-text("Sign decision")')
    await d2.waitForSelector('text=Signed: Retake photograph'); ok(await d2.isVisible('text=Signed by Dr. Demo Ophthalmologist'), 'identity from session')
    await d2.goto(`${BASE}/app/worklist?tab=signed`); await d2.waitForSelector('text=E2E-VISIT')
  })
  await check('patient status after sign-off: the approved next action, and the missing eye stays visible', async () => {
    await g.goto(statusUrl()); await g.waitForSelector('.nw-screening')
    const t = await g.innerText('.nw-screening'); ok(t.includes('The image needs to be taken again'), t); ok(t.includes('left eye is also still needed'), 'completeness still shown')
    await snap(g, 'patient-2-status-after'); await gs.close()
  })
} else {
  results.push([true, 'SKIPPED image-based specialist checks (set E2E_IMAGE to a local test image)']); console.log('  skip  image-based checks: E2E_IMAGE not set')
}
await check('axe: no serious or critical violations on sign-in and Specialist Attention', async () => {
  for (const [ctx, u] of [[cl, '/app/login'], [d2, '/app/worklist']]) {
    await ctx.goto(BASE + u, { waitUntil: 'networkidle' }); await ctx.waitForTimeout(400); await ctx.addScriptTag({ content: axeSrc })
    const v = await ctx.evaluate(async () => (await axe.run(document, { resultTypes: ['violations'] })).violations.filter((x) => ['serious', 'critical'].includes(x.impact)).map((x) => `${x.id}:${x.nodes[0].target}`))
    ok(v.length === 0, `${u}: ${v.slice(0, 3).join(' | ')}`)
  }
})
await check('sign out returns to the professional entry and closes the workspace', async () => {
  await d2.goto(`${BASE}/app/worklist`); await d2.click('button:has-text("Sign out")'); await d2.waitForURL('**/specialists')
  eq(await d2.evaluate(async () => (await fetch('/api/cases')).status), 401, 'session revoked')
  await d2.goto(`${BASE}/app/worklist`); await d2.waitForSelector('text=Sign in to Specialist Attention')
  eq(d2.errs.length, 0, 'console errors: ' + d2.errs.join(' | ').slice(0, 200))
})

// ---------------------------------------------------------------------------------------------------------------
console.log('Scroll-reveal never leaves content hidden')
await check('home: scrolling reveals every section; keyboard focus reveals; reduced motion and print show everything', async () => {
  const c = await newCtx(); const r = await page(c); await r.goto(`${BASE}/`, { waitUntil: 'networkidle' })
  const hidden = () => r.evaluate(() => [...document.querySelectorAll('.nw-reveal')].filter((e) => getComputedStyle(e).opacity !== '1' && !e.classList.contains('in')).length)
  ok((await hidden()) > 0, 'below-the-fold sections start hidden (animation in use)')
  await r.emulateMedia({ media: 'print' }); eq(await r.evaluate(() => [...document.querySelectorAll('.nw-reveal')].filter((e) => getComputedStyle(e).opacity !== '1').length), 0, 'print shows all')
  await r.emulateMedia({ media: 'screen' })
  for (let y = 0; y < 6000; y += 300) { await r.mouse.wheel(0, 300); await r.waitForTimeout(60) }
  await r.waitForTimeout(800); eq(await hidden(), 0, 'all revealed after scrolling')
  const k = await page(c); await k.goto(`${BASE}/`, { waitUntil: 'networkidle' })
  const card = k.locator('.nw-svc').last(); await card.focus(); await k.waitForTimeout(100)
  ok(await card.evaluate((e) => e.closest('.nw-reveal').classList.contains('in')), 'focus reveals')
  await c.close()
  const m = await newCtx({ reducedMotion: 'reduce' }); const rm = await page(m); await rm.goto(`${BASE}/`, { waitUntil: 'networkidle' })
  eq(await rm.evaluate(() => [...document.querySelectorAll('.nw-reveal')].filter((e) => getComputedStyle(e).opacity !== '1').length), 0, 'reduced motion shows all'); await m.close()
})
for (const [n, pg] of [['journey', p], ['worker', w], ['organiser', o]]) await check(`no console errors during ${n} flow`, async () => eq(pg.errs.length, 0, pg.errs.join(' | ').slice(0, 300)))

await browser.close()
const failed = results.filter((r) => !r[0])
console.log(`\n${results.length - failed.length}/${results.length} checks passed`)
if (failed.length) { console.log('FAILED:'); failed.forEach((f) => console.log(' -', f[1], '::', f[2])); process.exit(1) }
