# DrishtiQ Network — Implementation Blueprint

> Status: PLAN APPROVED, IMPLEMENTATION NOT STARTED. No branch created, nothing committed. Development begins only on explicit instruction (Phase 0 first; branch base still undecided, see Part 11).
> Evidence labels: **[V]** verified in repo / official docs on 2026-11-01. **[A]** assumption or recommendation. **[?]** not verified, check before relying on it.

---

## 0. Context

DrishtiQ today is a clinical AI screening workspace (grading, segmentation, Grad-CAM, review, reports). It does nothing for the people who never reach a screening. **DrishtiQ Network** adds a community-facing, voice-first module (awareness, camp discovery, interest registration, optional accounts, health-worker and organiser tools) and **DrishtiQ Saathi**, a bilingual voice assistant. It lives in the same repo, but with its own routes, router, DB file, auth, and code. It never touches clinical data.

Positioning: *Connecting Communities. Protecting Vision.* It is a prototype of a proposed ecosystem, not a deployed network. No real partnerships, appointments or camps are claimed.

Non-goals: touching models/checkpoints/inference/Grad-CAM/calibration, the clinical DB (`data/app/cases.sqlite`), existing `/api/*` endpoints, or the known issue that clinician review does not propagate to final reports (`docs/DRISHTIQ_TEAM_TECHNICAL_HANDBOOK.md:221-225`). Network neither fixes nor hides it.

---

## PART 1 — PRODUCT VISION

**Tagline pair:** DrishtiQ AI analyses retinal images. DrishtiQ Network connects people to screening. DrishtiQ Saathi lets them just *talk*.

### Personas and what each gets

| Persona | Needs | Gets |
|---|---|---|
| Rural patient / low literacy | Spoken help, pictures, 1 action per screen | Home with a giant "बोलकर पूछें / Talk to Saathi" orb, icon-led choices, spoken answers |
| Older adult | Big text, big targets, no timeouts | 18px+ base text, 56px targets, no auto-advance, "Read aloud" on every card |
| Community health worker | Fast assisted registration, follow-ups | Simplified portal: assisted registration with consent, my camps, my follow-ups |
| Organiser (NGO/hospital) | Plan camps, see demand | Camp CRUD, registration counts, capacity (labelled demo data) |
| Ophthalmologist | Know how Network feeds clinical review | "How it connects" page, no clinical access from Network |
| Judge | Purpose in 10-15 s | Hero + Saathi + one clear 2-3 min demo path |

### Core journeys
1. **Ask & find (guest):** Home → Saathi (voice/text) → "gaon mein aankhon ki jaanch" → PIN → real camp cards → camp detail.
2. **Register interest (guest):** camp → 3-step wizard (who, where/contact optional, consent) → server confirms → status page. States "Interest received", never "Appointment booked".
3. **Learn:** Awareness Hub → topic card → illustrated short story + audio → next step (find a camp).
4. **Return:** optional signup → My DrishtiQ → profile, registrations with real status, reminder prefs.
5. **Assisted:** health worker logs in → registers someone with them present, consent captured → follow-up task.
6. **Plan:** organiser creates a camp → it appears in public search (if verified) → counts update.

### Honesty rules (product-wide)
- Every camp shows one of **Verified / Unverified / Simulated (Demo) / Expired / Closed**, always with icon + text, never colour alone.
- Seeded camps are `source=demo_seed`, `verification=simulated`, with a persistent "DEMONSTRATION" ribbon, no real phone numbers, no named real hospitals.
- Registration = "interest". Only an organiser/health worker action can move it to `confirmed_by_organiser`; the UI wording says exactly that.
- No impact statistics, no government affiliation, no real partner logos.

---

## PART 2 — REPOSITORY INTEGRATION

### 2.1 Verified repo facts that drive the design [V]

| Area | Fact | Consequence |
|---|---|---|
| Router | `frontend/src/app/router.ts` (73 lines): `Route` union, `parse()`, `href()` adds `/app` prefix, `navigate()` dispatches cancelable `drishtiq:before-navigate`, `linkProps()`, `useRoute()`; `APP_PATH` legacy-redirect regex | Preserve it. Network gets **its own sub-router** (`frontend/src/network/netRouter.ts`) reusing `navigate/linkProps/useRoute`; `router.ts` only gains `{name:'network'}` + `/network` prefix handling. Check `APP_PATH` never swallows `/network/*` |
| App/Shell | `App.tsx:58` early-returns `<Landing/>` for `landing`, other routes render in `Shell` (sidebar `NAV` at `Shell.tsx:9`) | Network renders **outside** `Shell` with its own `NetworkShell` (clinical sidebar is wrong for the public). Same pattern as Landing |
| Both files already modified & uncommitted | `router.ts`, `Shell.tsx`, `App.tsx` have redesign edits | **Branch base is undecided.** Risk recorded in Part 11, decide before Phase 0 |
| Design system | `frontend/src/design/components.tsx` (Button, Field, Input, Select, Checkbox, Segmented, Switch, Tabs, Badge, Modal, Toast, Alert, Card, EmptyState, Skeleton, Progress, Avatar, Table…); `ds.css` scoped under `.ds`; `tailwind.config.js` **replaces** spacing/fontSize/colors/radius scales from `design/tokens.json` + `frontend/src/design/theme.json`, `preflight:false` | Reuse components (they inherit tokens). Network tokens go in a scoped CSS layer, **not** `tokens.json` |
| `tokens.json` is guarded | Consumed by `backend/report.py:20`, `src/inference/pipeline.py:79`, hashed in `configs/app/checksums.json:7`, checked by `preflight.py:70` | **Do not edit.** Use `.nw{--nw-*}` variables + a Network Tailwind-free CSS file |
| Dark mode / i18n | None. Light only, English strings hardcoded; only Hindi is the report toggle (`Report.tsx:11,54`) | Light only for Network. Build a small i18n layer in `frontend/src/network/i18n/` |
| Devanagari font | **None loaded** (Inter + DM Serif Display have no Devanagari) | Add self-hosted `@fontsource/noto-sans-devanagari`. `ui-regression.test.tsx:131-136` asserts no external URLs in the build, so no CDN fonts |
| Motion patterns | `landing.css` (`--motion-out`, `prefers-reduced-motion: no-preference` gating, `@media (hover:hover)`), `EyeFilm.tsx` (reduced-motion + saveData + visibility pause + user override) | Reuse the same pattern for all Network motion |
| Assets | `src/assets/landing/screening_camp.webp` (village camp illustration), eye footage with **credit obligation** (`eye/CREDITS.md`) | Reuse the illustration as interim hero art. Avoid the stock footage on Network, or keep its credit |
| Backend | `backend/app.py` is **monolithic, no APIRouter, no auth, no middleware/CORS**. Catch-alls: `/api/{path:path}` JSON 404 at line 488, then `/report-fonts`, `/assets`, SPA fallback at 499-506 | Add an `APIRouter` and `include_router` **before line 488**. SPA fallback already serves `/network/*` |
| Lifespan | `app.py:80-102` loads models, opens `store.connect()` into `state["db"]` | Open Network DB **before** the model-load try-block so Network works even if models fail; close explicitly on shutdown |
| Store | `backend/store.py`: single global sqlite connection, `Lock` on writes, `IF NOT EXISTS` + inline `PRAGMA table_info` migrations, DB at `RS_DATA_DIR or ROOT/data/app/cases.sqlite`; no FKs, no WAL | New `backend/network/db.py` → **separate** `network.sqlite`, same dir resolution (resolved at connect time, not import time, since tests monkeypatch `store.DIR`: `backend/test_api.py:17-23`), `foreign_keys=ON`, `WAL` |
| Deps | `requirements-app.txt`: fastapi 0.115.6, uvicorn, python-multipart only. `requirements-lock.txt` (venv) includes `argon2-cffi 25.1.0`, `httpx 0.28.1`, `python-dotenv 1.2.4`, `pydantic 2.14.1`, `pytest 8.3.4`, `Jinja2` | Add to `requirements-app.txt`: `argon2-cffi`, `httpx`, `python-dotenv`. No passlib/JWT libs needed |
| Secrets | No `.env` pattern. `.gitignore` ignores `.env*`, **`*secret*`, `*token*`, `*credential*`** (silently!) | Add `.env.example`. **Never name a file `*token*`/`*secret*`/`*credential*`** (use `sessions.py`, `keys.py`) |
| Tests | Backend: `backend/test_api.py` (TestClient loads real models!), root `tests/*.py`, `preflight.py`. Frontend: no framework; `frontend/tests/ui-regression.test.tsx` via `node:test` + custom `register-ts.mjs`, run `node tests/run-ui-checks.mjs` after build; `axe-core` devDependency + `?axe=1` hook | Network backend tests build a **lightweight FastAPI app with only the Network router** (no model load). Frontend tests extend the existing `node:test` runner; Playwright is optional (Part 9) |
| Vite | `/api` proxied to `127.0.0.1:8000` (`vite.config.ts:25`) | Voice/Saathi calls go via same-origin `/api/network/*`, so cookies and no CORS work in dev and prod |
| Skills | Session has no frontend-design skill. User-level `C:\Users\Asus\.agents\skills\` has `impeccable`, `frontend-design`, `emil-design-eng`, `web-design-guidelines`, `break-ui`, hooked via `.codex/hooks.json` (Codex) | **[?]** Whether Claude Code can see these is untested. Plan does not depend on them. If visible, use `frontend-design`/`web-design-guidelines` during UI phases. Nothing installed |

Discrepancy vs the brief: the brief lists `backend/store.py` as storage abstraction; it is a thin single-connection helper (no ORM, no migrations framework). Plan matches that style (plain `sqlite3`).

### 2.2 Why integrated, not standalone
Same origin gives cookie sessions, `/api` proxy, one start script (`start.bat`), shared brand and components. A separate site would need CORS, a second deploy, and duplicate the design system. No compelling reason to split.

### 2.3 Proposed directory structure (nothing created yet)

```
backend/
  network/
    __init__.py
    router.py              # APIRouter(prefix="/api/network"), mounts sub-routers
    config.py              # env + settings (provider order, limits, retention)
    db.py                  # network.sqlite connect(), schema, migrations, lock
    schema.sql             # canonical DDL
    models.py              # Pydantic request/response models (strict, extra=forbid)
    security.py            # argon2 hashing, session create/verify, rate limit, csrf/origin check
    deps.py                # require_user / require_role / require_camp_scope dependencies
    audit.py               # append-only audit writer
    services/
      camps.py             # search, detail, state (open/closed/expired) computation
      registrations.py     # create/dedupe/status transitions
      accounts.py          # signup/login/profile/delete/export
      workers.py           # assignments, assisted registration, follow-ups
      campaigns.py         # organiser CRUD + summaries
      content.py           # awareness content loader (versioned JSON)
    routes/
      public.py  accounts.py  registrations.py  worker.py  organiser.py  saathi.py
    saathi/
      engine.py            # ConversationEngine protocol + provider selection
      providers/
        rules.py           # deterministic fallback (always available)
        gemini.py          # Gemini text w/ function calling (optional, needs key)
        gemini_live.py     # ephemeral-token minting for Live (stretch)
      tools.py             # allowlisted tool registry + JSON schemas
      guardrails.py        # grounding check, PII scrub, refusal templates
      nlu.py               # PIN/district/language extraction, Hinglish normaliser
      templates.py         # hi/en response templates (the "speaker" for facts)
    seed/
      demo_camps.json      # clearly simulated
      awareness_hi_en.json # reviewed-status per item
    test_network_*.py
frontend/src/network/
  NetworkApp.tsx           # route switch for /network/*
  netRouter.ts             # Network route table + parse (reuses navigate/linkProps/useRoute)
  NetworkShell.tsx         # public shell: top bar, language switch, mobile tab bar, Saathi launcher
  network.css              # .nw scoped tokens, motion, layout
  netTheme.ts              # token constants for TS use
  api.ts                   # network API client (reuses request pattern of app/api.ts)
  i18n/ index.ts hi.ts en.ts useT.ts
  screens/
    NetworkHome.tsx  SaathiScreen.tsx  AwarenessHub.tsx  AwarenessTopic.tsx
    CampFinder.tsx   CampDetail.tsx    RegisterInterest.tsx  RegistrationStatus.tsx
    SignUp.tsx  Login.tsx  MyDrishtiQ.tsx
    worker/ WorkerLogin.tsx WorkerHome.tsx AssistedRegistration.tsx WorkerFollowUps.tsx
    organiser/ OrganiserHome.tsx CampEditor.tsx CampaignSummary.tsx
    NetworkAbout.tsx       # how it connects to clinical DrishtiQ + disclaimers
  components/
    SaathiOrb.tsx  LanguageToggle.tsx  CampCard.tsx  VerificationBadge.tsx
    BigChoice.tsx  ReadAloud.tsx  StepWizard.tsx  ConsentBlock.tsx  TopicCard.tsx
    PinInput.tsx   StatusTimeline.tsx  EmptyNote.tsx  TabBar.tsx
  saathi/
    types.ts               # SpeechInput, SpeechOutput, ConversationClient interfaces
    useSaathi.ts           # state machine (idle/listening/thinking/speaking/error)
    webSpeechInput.ts      # Web Speech API STT
    speechSynthesisOutput.ts
    conversationClient.ts  # calls /api/network/saathi/turn
    liveClient.ts          # stretch: Gemini Live via ephemeral token
    actions.ts             # whitelisted UI actions from server (navigate, open_form…)
  assets/                  # illustrations (SVG/WebP), see Part 3.7
frontend/tests/network-*.test.tsx
```

### 2.4 Architecture diagram

```mermaid
flowchart LR
  subgraph Browser
    UI[Network UI /network/*] --> NR[netRouter]
    UI --> SU[Saathi UI orb + transcript]
    SU --> SI[SpeechInput\nWeb Speech STT]
    SU --> SO[SpeechOutput\nspeechSynthesis]
    SU --> CC[ConversationClient]
  end
  CC -- same-origin /api/network/saathi/turn --> SR
  UI -- /api/network/* cookie session --> API
  subgraph FastAPI app.py
    API[Network APIRouter\nincluded before catch-all] --> AUTH[deps: session + role + scope]
    API --> SVC[services: camps registrations accounts workers campaigns]
    SR[saathi route] --> ENG[ConversationEngine]
    ENG --> P1[Gemini free tier\noptional]
    ENG --> P2[rules provider\nalways on]
    ENG --> TR[Tool Router allowlist + validation]
    TR --> SVC
    GR[Guardrails grounding + PII scrub] --- ENG
    CLIN[Existing clinical /api/* routes\nUNCHANGED]
  end
  SVC --> NDB[(network.sqlite)]
  CLIN --> CDB[(cases.sqlite)]
  NDB -. no FK / no query path .- CDB
  P1 -. HTTPS, anonymised text only .-> G[(Gemini API)]
```

Isolation guarantees: Network code never imports `backend/store.py` (except for resolving the data dir constant), never opens `cases.sqlite`, and no route/tool accepts a clinical id. A static test greps that `backend/network/**` does not reference `cases`/`reviews`/`state["db"]`.

---

## PART 3 — UI/UX DESIGN DIRECTION

### 3.1 Identity: "Dawn Clinic"
Keep DrishtiQ's recognisable blue (brand-700 `#263F83` from `theme.json`) and the eye mark, but shift mood from clinical-cool to **warm morning light**.

### 3.2 Colour system (scoped `.nw`, not in `tokens.json`) [A]

| Token | Value | Use |
|---|---|---|
| `--nw-bg` | `#FBF7F0` (warm paper) | page |
| `--nw-surface` | `#FFFFFF` | cards |
| `--nw-ink` | `#1B2440` | text (≥ 12:1 on bg) |
| `--nw-ink-soft` | `#4A5470` | secondary (verify ≥ 4.5:1) |
| `--nw-brand` | `#263F83` | primary actions, links (existing brand) |
| `--nw-saffron` | `#E8892B` → text-safe `#9A5200` | warm accent, highlights (decorative only at light value) |
| `--nw-sage` | `#2F7D6B` | "verified", success |
| `--nw-sky` | `#E6EEFB` | soft panels |
| `--nw-warn` | `#B45309` / bg `#FFF4E0` | unverified/expired |
| `--nw-danger` | `#B3261E` | errors |
| `--nw-orb-*` | brand→sky→saffron gradient | Saathi orb |

All pairs must pass the repo's checker (`scripts/check_contrast.py`) logic; statuses always pair colour with **icon + text**.

### 3.3 Typography
- Latin display: **DM Serif Display** (already bundled) for headlines. Latin body: **Inter** (already bundled).
- Devanagari: **Noto Sans Devanagari** (new, self-hosted, weights 400/600/700) for body and headings in Hindi; Devanagari glyphs are not in the current fonts. Hindi line-height 1.6, no letter-spacing, no uppercase transforms, `lang="hi"` on all Hindi nodes.
- Scale: base **18px** (vs app 15px), large text mode toggle (A / A+ / A++), min target **56px** (WCAG minimum 44px; larger for older adults/touch).

### 3.4 Layout philosophy
Editorial: one idea per viewport, big illustration + short sentence + one big button. Max 2 choices competing per screen. Generous whitespace, 8-pt grid, card radius from existing `radius.xl`. No dense tables in public screens. Tables only in organiser view.

### 3.5 Navigation
- **Top bar (desktop/tablet):** Brand lockup (link to Network home), 5 items: Home · Saathi · Find a camp · Learn · My DrishtiQ, plus language toggle `हिंदी | EN` (always visible, never in a menu), "DrishtiQ AI" cross-link (to `/`).
- **Mobile:** bottom tab bar (icon + label, 5 items) so everything is thumb-reachable; persistent "Home" tab; floating Saathi mic launcher on every public screen except Saathi.
- Health Worker and Organiser entry via a small footer link "For health workers / organisers" (kept separate from the public simple flow).
- Every deep screen has a big "← वापस / Back" and "घर / Home".
- Network home link back to clinical `/` is in footer + top bar.

### 3.6 Visual components (new, built on existing primitives)
`SaathiOrb`, `BigChoice` (icon-tile choices), `CampCard`, `VerificationBadge` (icon + text), `ReadAloud` button (speaker icon on every card), `StepWizard` (progress "Step 2 of 3", one question per step), `PinInput` (6 numeric boxes, `inputmode=numeric`), `StatusTimeline` (registration status with text), `ConsentBlock`, `TopicCard`, `TabBar`, `LanguageToggle`.
Existing reuse: Button, Field, Input, Alert, Modal, Toast, Skeleton, Switch, Card, Badge, Progress, EmptyState, Table (organiser).

### 3.7 Imagery and proposed assets (NOT generated; approval needed separately)

| Asset | Purpose | Spec | Interim |
|---|---|---|---|
| Hero illustration "Village morning screening" | Home hero; explains purpose at a glance | Warm flat illustration, health worker + elder + camp tent + eye motif, 2400×1350 WebP + SVG overlay layers for gentle parallax | Existing `screening_camp.webp` |
| 6 awareness topic illustrations | Topic cards (what is DR, why screen, what happens, myths, diabetes & eyes, next steps) | Consistent set, 1:1, SVG preferred, no text inside (text is localised) | Lucide icons on tinted tiles |
| Saathi orb | Signature element | **Code only** (CSS/canvas gradient), no image | n/a |
| Optional 6-s hero loop | Premium feel | Muted, reduced-motion/saveData safe, poster fallback (reuse `EyeFilm` logic) | Static hero |
| Hindi voice samples | Fallback where no hi-IN TTS voice | **Not generated**, shown as text-only + warning (Part 5) | n/a |

### 3.8 Animation (purposeful, reduced-motion safe)
Easing `--motion-out: cubic-bezier(.16,1,.3,1)` (same as landing). Allowed: hero fade/translate on arrival, card hover lift (hover:hover only), step-to-step slide, orb state transitions, subtle skeletons. Everything under `@media (prefers-reduced-motion: no-preference)`; under `reduce`: no movement, orb becomes a static ring + text label, transitions ≤ 0 ms (global rule exists in `ds.css`; Network repeats it for `.nw`). Also `forced-colors` block like `landing.css`. Motion never carries meaning on its own.

### 3.9 Saathi presentation
A large soft orb (160-240px) on a calm gradient stage:

| State | Orb | Text label (always) | Extra |
|---|---|---|---|
| idle | slow breathing glow | "बोलने के लिए दबाएँ / Tap to talk" | 3 suggestion cards |
| listening | ring pulses; amplitude-reactive if analyser available, else steady pulse | "सुन रही हूँ… / Listening…" | live transcript, Stop |
| thinking | rotating gradient arc | "सोच रही हूँ… / One moment…" | text kept visible |
| speaking | waveform-ish ripples | "बोल रही हूँ… / Speaking…" | Stop, Replay |
| error | amber ring | plain-language reason + "Type instead" | action button |

Beneath: short transcript bubbles (last 2-3 turns), **action cards** (camp results, "Register interest", "Open Awareness"), always-visible **text box** and **language chips**. No cartoon face, no claim of being human; disclosure line "Saathi is an AI helper." Voice gender: brief's examples are feminine (*karti hoon*); persona strings are templated so this can be neutral or switched **[A, non-blocking]**.

### 3.10 Mobile experience
Mobile-first. Bottom tab bar, sticky primary button above keyboard, wizard uses full-screen steps, camp results as stacked cards (no map dependency), safe-area insets, 16px inputs (iOS zoom), tested at 320px width.

### 3.11 Accessibility and low-literacy (concrete)
Icon+text choices, ≤ 8-word labels in simple Hindi, spoken prompt per screen via `ReadAloud`, one primary action per step, 56px targets, no time limits, confirm-before-submit review screen ("आपने यह भरा है… सही है?"), undo/edit at every step, preserved form state on error, visible language switch, home reachable always, skip links, focus management on route change (reuse App's `#main-content` focus pattern), `aria-live` for Saathi transcript and status, labelled orb button (`aria-pressed`), keyboard: Space/Enter toggles mic, Esc stops speech. Colour-independent statuses. Large-text mode. Plain-language errors (never HTTP codes).

### 3.12 How Network stays connected to DrishtiQ
Same brand blue + eye mark + DM Serif headlines + shared Button/Field/Alert behaviour and focus ring. Differentiators: warm paper background, saffron accent, 18px type, editorial layout, orb. Footer disclaimer links to "How this connects to DrishtiQ AI".

---

## PART 4 — SCREEN INVENTORY

Priority: **P0** = Plan A checkpoint, **P1** = Plan B, **P2** = stretch.

| # | Screen / route | Audience | Purpose & core function | Major sections | Interaction | API | States / edge cases | Pri |
|---|---|---|---|---|---|---|---|---|
| N1 | Home `/network` | everyone, judges | Explain in 10 s, route to 5 actions | Hero (illustration + 1 sentence) · primary: Talk to Saathi (orb) · 4 BigChoice tiles (Find camp, Learn, Register interest, Health worker) · "How it works" 3-step strip · demo disclaimer · footer | Orb tap opens Saathi; tiles navigate; hero parallax (motion-safe) | `GET /api/network/public/summary` (counts of non-expired camps; optional) | loading skeleton; backend down → static content still renders with notice | P0 |
| N2 | Saathi `/network/saathi` (+ floating launcher) | everyone | Voice/text conversation with real actions | Orb stage · transcript · suggestion cards · action cards · text input · language chips · privacy note | See 3.9; permission prompt with explanation first | `POST /saathi/turn`, `GET /saathi/capabilities` | mic denied, unsupported browser, no speech, no hi voice, quota exhausted → rules fallback, offline, slow net (>6 s "still working" + cancel) | P0 |
| N3 | Awareness Hub `/network/learn` | public | Visual topic grid | 6 TopicCards, "myth vs fact" strip, search-free | Tap → topic; speaker icon plays summary | `GET /content?lang=` | content missing → fallback to en with notice; "reviewed" vs "illustrative" badge | P0 |
| N3b | Topic `/network/learn/:slug` | public | Short storytelling content + audio | Illustration · 3-5 short blocks · ReadAloud · "Find a camp" CTA · reviewed-status note | Next/prev topic | same | long Hindi text wrapping; TTS missing | P0 |
| N4 | Camp Finder `/network/camps` | public | Search & browse | PIN input (6-digit) · district/city text · "near me" omitted (privacy) · results list · filters (open only default) · verification legend | Validate PIN client+server; empty state explains and offers "Register interest anyway"/Saathi | `GET /camps?pin&q&district&include_expired` | invalid PIN (inline Hindi/English message), no results (explicit "no verified camps found"), only simulated results (labelled), loading, error/retry | P0 |
| N4b | Camp Detail `/network/camps/:id` | public | Full info + CTA | Name · date/time · place · organiser · verification badge · availability text ("Interest open" / "Closed") · price **only if verified, else "Not provided"** · contact (verified only) · "Register interest" | Add to calendar omitted (P2) | `GET /camps/:id` | expired/closed disables CTA with reason; 404 friendly | P0 |
| N5 | Register interest `/network/camps/:id/register` | public | 3-step wizard | Step1 name or display ref + language · Step2 village/PIN + optional phone/email (labelled voluntary) · Step3 review + consent checkbox (large) + submit | Per-step validate; edit from review; idempotency key; Saathi can pre-fill but cannot submit | `POST /registrations` | duplicate → friendly "You already showed interest" with existing status; closed camp; network error preserves form + retry; server 422 mapped per field | P0 |
| N5b | Status `/network/registrations/:ref` | guest (with ref + secret) / user | Show real status | Timeline: Interest received → Contacted → Confirmed by organiser → Attended; plain-text status, last updated | Guest access via `ref` + one-time `receipt_code` shown at submit (not guessable) | `GET /registrations/lookup` (POST with ref+code) | invalid code (rate-limited); cancelled | P0 |
| N6 | Sign up `/network/signup` | public | Optional account | Name · identifier (mobile **or** email) · password · PIN/village · language · reminder prefs · consent · note "No account needed to use Network" | One screen per group (3 steps); show-password toggle | `POST /auth/signup` | weak password, duplicate identifier (generic message), rate-limited | P0 |
| N7 | Login `/network/login` | public | Return users | Identifier + password · "Forgot?" (prototype: explains admin reset; no email service) | Remember session cookie | `POST /auth/login`, `POST /auth/logout` | lockout message; generic failure | P0 |
| N8 | My DrishtiQ `/network/me` | registered user | Personal dashboard | Greeting · profile card (edit) · My registrations (with status) · Reminder prefs (Switch) · Recommended reading · "Download/Delete my data" · Sign out | Inline edit; Saathi shortcuts | `GET/PATCH /me`, `GET /me/registrations`, `DELETE /me`, `GET /me/export` | unauthenticated → login with return-to; empty registrations → CTA | P0 |
| N9 | Worker login `/network/worker/login` | health workers | Real auth, **no role switch** | Username/password; banner showing `PROTOTYPE ACCOUNT` when seeded | Same auth as users, role=health_worker | `POST /auth/login` | 403 non-worker | P1 |
| N10 | Worker home `/network/worker` | health workers | Operational overview | My camps · pending interest requests · my follow-ups · "New assisted registration" | Large cards; list view not table | `GET /worker/camps`, `/worker/requests`, `/worker/followups` | scope: only assigned camps | P1 |
| N11 | Assisted registration `/network/worker/assist` | health workers | Register someone with them | Same wizard + "I am registering on behalf of the person" + **spoken/written consent confirmation by the person** + ownership shown ("Recorded by worker X, can be claimed by the person") | Consent step cannot be skipped | `POST /worker/registrations` | duplicates; phone-sharing consent separate | P1 |
| N12 | Follow-ups `/network/worker/followups` | health workers | Track tasks | Task cards: contact person · confirm attendance · screening done · mark outcome | Mark complete, add short note (no clinical notes) | `PATCH /worker/followups/:id` | permission checks | P1 |
| N13 | Organiser home `/network/organiser` | organisers | Plan camps | Camp list + status chips · summary tiles (registrations, capacity, attendance) · small bar chart of interest by PIN (only meaningful chart) | Create/edit camp, publish/close | `GET/POST/PATCH /organiser/camps`, `GET /organiser/summary` | demo-data banner; validation (date in future, capacity ≥ 0) | P1 |
| N14 | Camp editor `/network/organiser/camps/:id` | organisers | CRUD | Form with live preview of the public card, verification field (admin-only) | Save draft/publish | same | conflict/validation | P1 |
| N15 | About / How it connects `/network/about` | judges, doctors | Honesty + clinical link story | Diagram: Awareness → Camp → Screening → DrishtiQ AI → Clinician review; "What is real / simulated" table; privacy; credits | Static | none | — | P0 |
| N16 | Not found / error boundary | all | Friendly recovery | Big "Home" + "Saathi" | — | — | — | P0 |

Saathi-driven navigation target set: home, camps (with prefilled PIN), a camp, register (prefilled), learn (topic), me, login, language.

---

## PART 5 — SAATHI TECHNICAL ARCHITECTURE

### 5.1 Option comparison (free-tier facts from official pages fetched 2026-11-01)

| Option | What | Cost / quota | Hindi/English | Privacy | Reliability | Verdict |
|---|---|---|---|---|---|---|
| **A. Browser Web Speech** (STT `SpeechRecognition`, TTS `speechSynthesis`) | No SDK, no key | Free, unlimited | STT: good on Chrome/Edge incl. `hi-IN`, `en-IN`; Safari partial; **Firefox no STT**. TTS: voices depend on OS; Android/Chrome usually has Hindi, desktop Windows may not **[?]** test | Chrome STT streams audio to the vendor's service (needs internet), so ask consent before mic | Variable by device; feature-detect | **Primary for speech I/O** |
| **B. Gemini text API, free tier** | Natural language + **function calling** via backend | Free-tier models listed on the pricing page [V]: Gemini 3.8/3.6 Flash, 3.5/3.1 Flash-Lite, 2.5 Flash/Flash-Lite, Gemma 4 and others. **RPM/RPD limits are per-project and not published on the pricing page** [V] → read them in AI Studio before choosing [?] | Strong Hindi/Hinglish | **Free tier: "content used to improve our products"** [V] → anonymous, non-personal text only | Quota/latency risk during demo | **Optional enhancer** behind the provider interface, with rules fallback |
| **C. Gemini Live API** | Real-time audio-to-audio, interruptions | Free tier lists *Gemini 3.8 Live*, *3.1 Flash Live Preview*, *2.5 Flash Native Audio* with free input/output [V on pricing page]; session limits & concurrency **not verified** [?]. Docs: raw PCM in 16 kHz / out 24 kHz, **ephemeral tokens recommended for browser clients** [V] | Native audio, likely good | Audio goes to Google; same free-tier data-use terms | WebSocket complexity, preview models, quota | **Stretch (Plan B+ spike)**: only after A+B work; no personal data; time-boxed; never the only path |
| **D. Others (Whisper/Piper local, etc.)** | Local STT/TTS | Free but heavy | OK | Fully local | Needs model downloads/CPU, no meaningful gain over A for a demo | **Not now** (Plan C) |

Do not promise barge-in unless the active mode supports it: Web Speech mode = tap-to-stop only; Live mode = real interruption.

### 5.2 Recommendation
- **Speech I/O:** Web Speech API (Option A) with feature detection and always-visible text input.
- **Conversation:** `ConversationEngine` with a provider chain: `gemini` (if `GEMINI_API_KEY` present, healthy, and quota not exhausted) → **`rules` (deterministic, always on)**. Automatic degradation on 429/timeout/5xx with a one-line notice ("Simple mode: AI helper is resting"). **Never a paid fallback**; the Gemini key must be an AI Studio free-tier key, and a config check refuses to start Gemini mode if `NETWORK_ALLOW_PAID` is not explicitly false (guards against accidentally using a billed project; actual billing status cannot be read from the key **[?]**, so also document "use a project without billing enabled").
- **Spike (optional, after Plan A checkpoint):** Gemini Live through ephemeral tokens minted by `/saathi/live-token` (backend holds the key), feature-flagged `NETWORK_LIVE=0` by default.

### 5.3 Turn pipeline

```
mic/text → (client) transcript, lang
POST /api/network/saathi/turn {text, lang, ui_context{screen, camp_id?}, history[last 6 anonymised turns], session csrf}
  server:
   1 sanitise + length cap (500 chars) + rate limit per IP/session
   2 nlu.py normalise Hinglish, extract PIN/language/intent hints
   3 PII scrub for provider-bound text (phones, emails, long digit runs, names given in profile) — PIN code is allowed (needed for search, not identifying alone)
   4 engine → provider returns {intent, tool_calls[]} (LLM acts as ROUTER)
   5 tool router validates args against JSON schema, checks authz, executes read-only tools
   6 response composer: facts (camps, dates, statuses, profile) rendered by templates.py in hi/en  (templates are the "speaker" for facts)
   7 optional LLM phrasing of non-factual smalltalk/awareness explanations from approved content only
   8 guardrails: grounding check (every camp id/name/date/price in reply must exist in tool results), banned-claim regex (diagnosis, "booked", "confirmed" unless status says so), medical-advice refusal template
   → {reply_text, lang, ui_actions[], cards[], provider_used, degraded}
```
Personal data design: **the LLM never receives profile or registration data.** For "meri profile dikhao" the LLM (or rules) only classifies the intent `show_profile`; the server then renders the answer from the DB via template and returns it to the client directly. Auth failures return a "please log in" template with a Login action card.

### 5.4 Tool (action) registry — allowlist, no free-form SQL

| Tool | Params (validated) | Authz | DB access | Output | Errors | Confirmation |
|---|---|---|---|---|---|---|
| `find_camps` | `pin` (`^\d{6}$`), `district?` (≤40 chars), `q?` | public | read `camps` joined `locations` where status open/upcoming; sort by PIN match then date | `[{camp_id,name,date,place,verification,state}]`, max 5 | invalid pin → ask again; none → explicit "no verified camps" template | none |
| `get_camp_details` | `camp_id` (int) | public | read | camp detail DTO (price/contact only if verified) | 404 → template | none |
| `get_awareness_content` | `topic` ∈ enum, `lang` | public | read content JSON | approved snippet + review flag | unknown topic → list topics | none |
| `navigate_to_section` | `target` ∈ enum | public | none | UI action `{type:'navigate', to}` | invalid → refuse | none (client navigates, user can go back) |
| `start_registration` | `camp_id`, optional prefill {name?, pin?, lang?} | public | read camp, check open | UI action `{open_form, prefill}`, **does not create** a record | closed camp → explain | **Submission only via UI Confirm button → `POST /registrations`**; LLM can never submit |
| `get_registration_requirements` | — | public | none | static list of fields + consent text | — | none |
| `get_supported_languages` | — | public | none | `[hi,en]` | — | none |
| `set_language` | `lang` ∈ {hi,en} | public (UI pref) or user (persist to profile) | write only if authed | UI action | invalid → refuse | none (reversible) |
| `show_my_profile` | — | **authed user** | read own row by session user id (never by param) | templated summary | 401 → login card | none |
| `list_my_registrations` | — | **authed user** | read where `user_id = session` | templated list with statuses | 401 → login | none |

Hard rules: tools take **no user id parameter** (identity comes from the session), strict Pydantic `extra=forbid`, per-session tool-call cap (5/turn), results capped, every call logged (no PII) to `audit` when state changing, plus a `saathi_events` counter (intent, tool, provider, latency, success) without raw text.

### 5.5 Voice state machine (frontend `useSaathi.ts`)
`idle → requesting_permission → listening → (final transcript) → thinking → speaking → idle`, plus `error(reason)`. Handles: permission denied (explain how to re-enable + typing), `no-speech`/silence timeout (8 s, prompt once then stop), `audio-capture` missing device, `network` error, unsupported browser (hide mic, show text first), low-confidence (show transcript for the user to confirm/edit before sending when `confidence < 0.6`), user pressing Stop mid-speech (`speechSynthesis.cancel()`), Replay (re-speak last reply), language mismatch (recognition `lang` follows UI lang; "Switch to Hindi?" chip), slow network banner, `visibilitychange` cancels speaking, one concurrent request (abort previous).
TTS: if no voice for the language, show text, a note, and still allow reading via device TTS settings guidance; never fail silently. Mic consent: pre-prompt dialog "Saathi will use your device's speech recognition. Your voice is not saved by DrishtiQ. Your browser's speech service may process it."; remember consent in memory only (sessionStorage for consent flag is acceptable).
Raw audio is never recorded or uploaded by DrishtiQ in Web Speech mode.

### 5.6 Security for Saathi
Keys only in backend env (`.env`, ignored; `.env.example` added); input caps and per-IP + per-session rate limits (protects free quota); prompt-injection stance: tool allowlist + schema validation + identity from session means injection cannot widen access; system prompt forbids diagnosis/treatment/prices/booking claims; outputs pass guardrails; logs exclude transcripts by default (optional debug flag off).

---

## PART 6 — BACKEND AND DATA ARCHITECTURE

### 6.1 Storage
`network.sqlite` beside `cases.sqlite` (path via same data-dir resolution at connect time). `PRAGMA foreign_keys=ON; journal_mode=WAL; busy_timeout=3000`. Schema via `schema.sql` + versioned `schema_migrations` table (small runner in `db.py`). All writes through a lock-protected helper (mirrors `store.py`). Migrations are never run until implementation is approved.

### 6.2 Entities (11 tables, kept minimal)

```sql
organisations(id PK, name, kind CHECK(kind IN('ngo','hospital','govt_programme_proposed','other')),
              verification CHECK(verification IN('verified','unverified','simulated')),
              created_at)
locations(id PK, org_id FK NULL, label, village, district, state, pin CHECK(pin GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'), lat NULL, lng NULL)
camps(id PK, org_id FK, location_id FK, title_hi, title_en, starts_at, ends_at,
      capacity INTEGER NULL CHECK(capacity IS NULL OR capacity>=0),
      price_info TEXT NULL,            -- shown only when verification='verified'
      contact_public TEXT NULL,        -- shown only when verification='verified'
      verification CHECK(IN('verified','unverified','simulated')),
      publish_state CHECK(IN('draft','published','closed','cancelled')),
      source CHECK(IN('demo_seed','organiser','admin')),
      created_by FK users, created_at, updated_at)
      -- derived (not stored): state = expired if ends_at<now; open if published & not full & not expired
users(id PK, role CHECK(IN('user','health_worker','organiser','admin')),
      display_name, identifier_type CHECK(IN('mobile','email')), identifier_norm UNIQUE,
      identifier_verified INTEGER DEFAULT 0,             -- unverified mobile is NOT identity
      password_hash,                                     -- argon2id
      village, pin, language CHECK(IN('hi','en')) DEFAULT 'hi',
      consent_version, consent_at, reminders_opt_in INTEGER DEFAULT 0, comm_pref,
      org_id FK NULL, created_at, deleted_at NULL, failed_logins INT, locked_until NULL)
sessions(id_hash PK, user_id FK, created_at, expires_at, last_seen, ip_hash, ua_hash)  -- opaque token stored hashed
registrations(id PK, public_ref UNIQUE,   -- e.g. DQN-7F3K-92 (random, non-sequential)
      camp_id FK NOT NULL, user_id FK NULL, created_by_user_id FK NULL,  -- worker if assisted
      display_name, village, pin, phone_enc/norm NULL, email NULL, language,
      dedupe_key UNIQUE,                 -- sha256(camp_id|normalised contact) or user_id|camp_id; NULL-safe via partial index for contact-less
      receipt_code_hash, idempotency_key UNIQUE,
      status CHECK(IN('interest_received','contacted','confirmed_by_organiser','attended','no_show','cancelled')),
      consent_version, consent_at, consent_scope,   -- includes separate flag contact_consent
      channel CHECK(IN('self','assisted','saathi_guided')),
      created_at, updated_at, purge_after)
worker_assignments(id PK, user_id FK, camp_id FK, UNIQUE(user_id, camp_id))
followups(id PK, registration_id FK, assigned_to FK NULL, kind CHECK(IN('contact','confirm_attendance','post_screening')),
          status CHECK(IN('open','done','cancelled')), note_short CHECK(length(note_short)<=200), due_at, updated_at)
content_items(id PK, slug, lang, kind CHECK(IN('topic','myth','fact')), title, body_json, review_status CHECK(IN('clinically_reviewed','illustrative','draft')), reviewed_by NULL, version)
audit_log(id PK, at, actor_user_id NULL, actor_role, action, entity, entity_id, detail_json_minimal, ip_hash)  -- append-only; no PII values
```
Languages table is replaced by CHECK enums (`hi`,`en`) plus per-language columns, avoiding an unnecessary table. Campaign grouping (`campaigns`) is deferred to P2: summaries are queries over camps/registrations; add a table only if multi-camp campaigns are demoed.

Future (designed, not built): `clinical_link_requests(user_id, patient_ref_hash, state, consent_at, approved_by)` for Plan C; see 6.6.

### 6.3 How the design prevents the listed problems

| Risk | Control |
|---|---|
| Duplicate registrations | `dedupe_key` unique + `idempotency_key` unique; duplicate returns existing status (200) not an error; contact-less guests dedupe by idempotency key + same device short window |
| Invalid camp reference | FK + service checks camp exists and `publish_state='published'` |
| Registration to closed/expired/full camps | service-level state check inside a transaction; capacity counted as non-cancelled registrations; "full" yields "interest list" wording only if organiser allows waitlist |
| Unauthorised admin actions | `deps.require_role`, organiser scoped to `org_id`, worker scoped by `worker_assignments`; admin via server-side seeded account only |
| False booking confirmation | status enum + wording table: only `confirmed_by_organiser` is rendered as "Confirmed by organiser"; UI/Saathi cannot set status; success response contains `status` echo and Saathi reads it from the DB, not from the LLM |
| Sensitive data exposure | minimal fields, no medical history, phone normalised and masked in lists (`98••••1234`), encrypted-at-rest is **not** claimed (same caveat as `store.py:3-5`); registrations visible only to owner/assigned worker/org organiser; receipts via unguessable codes, rate-limited |
| Cross-module corruption | separate DB file, no FKs to clinical, static test forbidding imports, no shared tables |
| Enumeration | random `public_ref`, generic login/signup errors, rate limits |

### 6.4 Auth and sessions (replaces any "demo role switch")
- **Guest:** no account; registrations produce `public_ref` + `receipt_code` (shown once, printable/Saathi-readable) to look up status.
- **Account identifiers:** mobile or email **as a login handle**, `identifier_verified=0` by default and shown as "not verified"; it is never treated as proof of identity, never used to auto-link anything. Free verification options for later: email magic link (needs SMTP, free-tier SMTP **[?]**) or admin/worker in-person verification at a camp; **no mandatory paid SMS OTP**.
- **Password:** argon2id via `argon2-cffi` (in the lock file, add to `requirements-app.txt`), min 8 chars (accept passphrases, no composition rules), common-password short denylist, show/hide toggle. Per-account lockout (5 fails → 15 min) + per-IP rate limit.
- **Session:** 32-byte random token, stored **hashed** in `sessions`, delivered as `HttpOnly; SameSite=Lax; Path=/; Secure when https` cookie, 7-day sliding expiry, rotate on login, delete on logout, revoke all on password change/delete.
- **CSRF:** state-changing requests require `Content-Type: application/json` + `Origin`/`Host` match check + `X-DQN-CSRF` header equal to a double-submit cookie.
- **Roles:** `user`, `health_worker`, `organiser`, `admin`. Workers/organisers/admin are created by a **local CLI** (`python -m backend.network.cli create-staff …`, a Plan step) or seed script, never self-service. Seeded prototype staff show a persistent `PROTOTYPE ACCOUNT` banner. No production claim.
- **Account deletion/retention:** `DELETE /me` hard-deletes profile+sessions, anonymises registrations (name→"Deleted", contact nulled) while keeping aggregate counts; guest registrations purge contact fields after `RETENTION_DAYS` (default 180, config); export endpoint returns the user's data as JSON.
- **Consent:** versioned consent text stored; contact-sharing consent separate from interest consent; reminder opt-in default off.

### 6.5 API endpoints (`/api/network/...`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/public/summary` | none | counts for home (open camps) |
| GET | `/camps` | none | search (`pin`, `district`, `q`, `include_expired`) |
| GET | `/camps/{id}` | none | detail |
| GET | `/content` , `/content/{slug}` | none | awareness (lang) |
| GET | `/languages` | none | supported languages |
| POST | `/registrations` | none/optional session | create interest (idempotent, consent required) |
| POST | `/registrations/lookup` | none | status by `public_ref`+`receipt_code` |
| POST | `/auth/signup` `/auth/login` `/auth/logout` | none/session | accounts |
| GET/PATCH/DELETE | `/me` | user | profile / delete |
| GET | `/me/registrations`, `/me/export` | user | own data |
| POST | `/me/registrations/{id}/cancel` | user | cancel own interest |
| GET | `/worker/camps` `/worker/requests` `/worker/followups` | worker | scoped lists |
| POST | `/worker/registrations` | worker | assisted registration (consent captured) |
| PATCH | `/worker/registrations/{id}/status` | worker/organiser | contacted/attended/no_show |
| PATCH | `/worker/followups/{id}` | worker | complete task |
| GET/POST/PATCH | `/organiser/camps` | organiser | CRUD (own org) |
| GET | `/organiser/summary` | organiser | counts by camp/PIN/status |
| POST | `/saathi/turn` | none/optional session | conversation turn |
| GET | `/saathi/capabilities` | none | which providers/voices modes are active |
| POST | `/saathi/live-token` | none (rate-limited) | **stretch**, mints ephemeral token, flag-gated |
| GET | `/health` | none | network module health |

Error format: JSON `{detail, code, field?}` with `code` machine-readable and the client maps `code` → localised plain-language message (reuse FastAPI `detail` pattern the existing client already parses in `app/api.ts` `request()`).

### 6.6 Clinical separation and future linking
No Network code reads `cases.sqlite`. Future (Plan C, separate approval): a consent flow where a **clinician/health worker with clinical authorisation** generates a one-time link code in the clinical module; the person enters it inside My DrishtiQ and explicitly consents; linkage stored as hashed `patient_ref` in `clinical_link_requests`; no name/phone matching, ever; clinical info shown only through an explicit, audited interface.

### 6.7 Integration with `backend/app.py` (minimal, additive)
1. `from backend.network.router import router as network_router`
2. Open/close `network.sqlite` in `lifespan`, before the models try-block.
3. `app.include_router(network_router)` **above** the `/api/{path:path}` 404 at line 488.
No existing route, model or response changes.

---

## PART 7 — FILE-BY-FILE IMPLEMENTATION MAP

### Existing files to modify (all additive)
| File | Change |
|---|---|
| `backend/app.py` | include router; lifespan open/close Network DB (≈ 8 lines) |
| `requirements-app.txt` | add `argon2-cffi`, `httpx`, `python-dotenv` (pin versions from lock) |
| `.gitignore` | ensure `network.sqlite*` ignored (already `*.sqlite`, `data/app/`), `!.env.example` already present |
| `frontend/src/app/router.ts` | add `{name:'network'}` and `/network` prefix; keep `APP_PATH` from capturing it |
| `frontend/src/app/App.tsx` | `if (route.name==='network') return <NetworkApp/>` before Shell (same pattern as `landing`), lazy-loaded |
| `frontend/src/app/screens/Landing.tsx` (+ `landing.css`) | header link + closing-section card to Network (small) |
| `frontend/src/app/Shell.tsx` | optional "DrishtiQ Network" link (P1; avoid mixing Network into clinical sidebar) |
| `frontend/package.json` | add `@fontsource/noto-sans-devanagari`, optionally `@playwright/test` (dev) |
| `frontend/tests/ui-regression.test.tsx` | add Network route/contract/a11y tests or new sibling test files + runner list |
| `README.md` | short Network section, env setup |
| `docs/` | `NETWORK_CONTENT_REVIEW.md`, `NETWORK_PRIVACY.md` |

**Do not touch:** `design/tokens.json`, `configs/app/checksums.json` entries, `src/inference/**`, `backend/store.py`, `backend/report*.py`, `backend/test_api.py`, model files.

### New files
All of Section 2.3 (backend `backend/network/**`, frontend `frontend/src/network/**`, `frontend/tests/network-*.test.tsx`), plus `.env.example`, `docs/NETWORK_*.md`, `backend/network/cli.py` (create-staff, seed-demo, purge-expired).

---

## PART 8 — DEVELOPMENT ROADMAP

Effort in focused engineering days (1 person, includes tests). Order optimises an early demo-able Plan A checkpoint.

| Ph | Task | Pri | Files | Depends | Approach | Outcome | Effort | Tests | Acceptance |
|---|---|---|---|---|---|---|---|---|---|
| 0 | Branch & baseline | P0 | git only | branch decision | Decide base (Part 11); create `feat/drishtiq-network`; run existing tests/build for baseline | Clean baseline recorded | 0.25 d | existing suites | baseline pass/fail list saved; no uncommitted work lost |
| 1 | Network DB + seed + public read APIs | P0 | `backend/network/{db,schema.sql,config,models,services/camps,services/content,routes/public,router}.py`, seed JSON, `app.py` | 0 | schema, seed demo camps (simulated), search by PIN/district, content | `/api/network/camps` works; clinical API unchanged | 1.5 d | pytest on lightweight app: search, empty, invalid PIN, expired, isolation grep test | all public endpoints return per spec; `pytest backend tests` baseline unchanged |
| 2 | Registration service | P0 | `services/registrations.py`, `routes/registrations.py`, audit | 1 | transactions, dedupe, idempotency, receipt codes, status wording | guest register + lookup | 1.5 d | duplicate, closed camp, invalid camp, replay idempotency key, rate limit | guest can register; duplicate returns same ref; closed camp rejected 409 |
| 3 | Frontend foundation | P0 | `network/{NetworkApp,netRouter,NetworkShell,network.css,netTheme,api,i18n/*}`, router/App edits, font dep | 1 | scoped tokens, tab bar, language toggle (persist), skeletons, error boundary | empty-but-navigable Network | 2 d | route tests, axe on shell, Hindi rendering snapshot | `/network` loads; `/app` screens unchanged; Hindi shows Devanagari font |
| 4 | Home + Camp Finder + Camp Detail | P0 | screens N1,N4,N4b + components | 1,3 | PIN input, results, badges, empty states | full camp discovery | 2.5 d | invalid PIN, none, network error, 320 px, large-text | every listing shows verification text+icon; demo ribbon visible |
| 5 | Registration wizard + status | P0 | N5,N5b, ConsentBlock, StepWizard | 2,4 | 3 steps, review, idempotent submit, receipt | end-to-end interest | 2 d | validation, duplicate, offline retry, keyboard-only | submit shows server-confirmed "Interest received" only |
| 6 | Awareness Hub | P0 | N3,N3b, content JSON, ReadAloud (TTS) | 1,3 | 6 topics hi/en with review flags | learn flow | 1.5 d | content fallback, TTS-missing | content labelled reviewed/illustrative |
| 7 | Rules-based Saathi + voice I/O (Plan A) | P0 | `saathi/*` backend rules+tools+guardrails+templates; frontend `saathi/*`, SaathiScreen, orb v1, launcher | 1,2,4,5 | NLU for Hindi/Hinglish/English, PIN capture, tools, STT/TTS, text fallback | Saathi finds camps, starts registration, navigates | 4 d | all voice scenarios (Part 9), tool schema fuzz, guardrail grounding tests | scripted dialogue "gaon mein jaanch → 453331" returns actual DB results; no-camps case honest |
| **A** | **PLAN A CHECKPOINT** | | | | | demo-ready MVP | | full regression | judge-path works with no API key and no paid service |
| 8 | Accounts + My DrishtiQ | P0/P1 | `security,deps,accounts`, N6,N7,N8, Saathi profile tools | 2,3,7 | argon2, sessions, CSRF, profile, own registrations, delete/export | optional login | 3.5 d | auth matrix, IDOR tests, lockout, session expiry, delete | user A never sees user B (tests); guest flows unaffected |
| 9 | Premium polish pass | P1 | `network.css`, orb v2, hero, transitions, illustrations | 3-8 | motion system, skeleton, micro-interactions, asset integration after approval | premium feel | 3 d | reduced-motion, forced-colors, visual checks at 5 widths | no motion under reduce; Lighthouse a11y ≥ 95 |
| 10 | Gemini provider + degradation | P1 | `providers/gemini.py`, config, `.env.example`, status chip | 7 | function calling to the same tool registry, PII scrub, quota/429 handling, auto fallback | more natural conversation | 2 d | mock provider tests (no real calls in CI), 429 → rules fallback, injection tests | works offline with no key; with key, no PII in outbound payload (unit-asserted) |
| 11 | Health worker portal | P1 | `workers.py`, `routes/worker.py`, N9-N12, CLI create-staff | 8 | scoped lists, assisted registration with consent, follow-ups | worker demo | 3 d | scope/IDOR tests, consent required | worker sees only assigned camps; assisted records show owner |
| 12 | Organiser dashboard | P1 | `campaigns.py`, `routes/organiser.py`, N13,N14 | 8,11 | camp CRUD, summary, one meaningful chart | planning demo | 2.5 d | org-scope, validation | organiser only edits own org; demo banner |
| 13 | About/How it connects, demo mode polish | P0/P1 | N15, docs | all | honesty table, diagram, reset-demo CLI | judge-ready | 1 d | content tests | clearly lists what is simulated |
| 14 | Gemini Live spike (optional) | P2 | `gemini_live.py`, `liveClient.ts` | 10 | ephemeral tokens, PCM streaming, flag off by default | proof of low-latency | 3 d (time-boxed) | manual, quota check | kill-switchable; app unaffected if off |
| 15 | Full QA, perf, a11y, docs | P0 | tests, docs | all | execute Part 9 matrix, bundle-size check (lazy-load Network) | release candidate | 2.5 d | everything | all acceptance rows green |

Totals: Plan A ≈ 15.25 d (phases 0-7 plus checkpoint), Plan B adds ≈ 17.5 d (phases 8-13, 15), optional spike 3 d. If time is short, cut order: spike → organiser dashboard → worker portal depth → Gemini provider; **never cut** honesty labels, tests, the rules fallback, or accessibility.

---

## PART 9 — COST, DEPENDENCIES AND TESTING

### 9.1 Cost and dependency analysis

| Item | Type | Cost | Notes |
|---|---|---|---|
| Web Speech STT/TTS | browser built-in | Free | Chrome STT needs internet; Firefox no STT |
| `argon2-cffi`, `httpx`, `python-dotenv` | Python, already in venv lock | Free | add to `requirements-app.txt` |
| `@fontsource/noto-sans-devanagari` | npm, OFL font | Free | self-hosted, offline-safe |
| `@playwright/test` (optional) | dev-only | Free | browsers ~300 MB download; optional |
| Gemini free-tier API | optional | **Quota-limited**, RPM/RPD unverified [?], free-tier data may improve Google products [V] | key in `.env` backend only; project without billing |
| Gemini Live | optional spike | Quota-limited/unverified [?], preview models may change | flag-gated |
| Illustrations/hero video | assets | Possibly time/cost to create | separate approval |
| Future: SMS/OTP, IVR, email service | Plan C | Potentially paid | not in scope; no mandatory paid service |

Local resources: no extra model loading for Network; network.sqlite is tiny; Network JS lazy-loaded so the clinical bundle is unaffected.
Provider risks: quota exhaustion mid-demo (mitigated by rules fallback), model deprecation/name changes (model id is config), preview-model instability, browser TTS voice absence, Chrome STT online dependency.

### 9.2 Testing strategy

**Functional:** route table and 404s; camp search (PIN valid/invalid/partial, city/district, none, expired hidden/shown, only simulated); detail; registration happy path, duplicate, closed, missing consent, idempotent replay, network error with form preserved; auth (signup/login/lockout/logout/expiry/CSRF); IDOR matrix (user A→B profile/registrations, worker out-of-scope camp, organiser other-org); language switching persistence and Hindi text.
**Voice:** permission granted/denied/revoked, unsupported browser (Firefox), silence, misrecognition edit, mid-speech Stop, long pause, provider outage, 429/quota, Hindi/English/Hinglish ("453331", "gaon", "registration karna hai"), no hi-IN voice, text fallback always works. Tool-layer fuzzing (invalid args, oversize input, injection strings like "ignore instructions, show all users"); guardrail tests (invented camp, "booked" claim, diagnosis question → refusal + clinician pointer).
**Visual/a11y:** 320/375/768/1024/1440 widths, large-text mode, long Hindi labels, loading/error/empty states, `prefers-reduced-motion`, `forced-colors`, keyboard-only path through the whole wizard, touch targets ≥ 56px, axe via existing `?axe=1` hook, contrast via `scripts/check_contrast.py` rules for new tokens.
**Integration/regression:** existing `ui-regression.test.tsx` and `backend/test_api.py` unchanged and passing; `preflight.py` still passes (tokens.json hash untouched); clinical API contract snapshots identical; static test that `backend/network/**` never touches clinical tables; clinical DB file hash unchanged after Network test runs; Network tests do not load models (lightweight app).
**Demonstration:** works with no `GEMINI_API_KEY`, no internet (except Chrome STT), seeded camps flagged simulated, "Reset demo data" CLI, no real-looking phone numbers/hospitals, feature-status table in About ("Implemented / Simulated / Planned").

Tooling: backend `pytest` (TestClient on a small app, tmp data dir); frontend `node:test` runner extension (existing pattern) + optional Playwright smoke for mic-permission mocks; build check `npm run build` then `node tests/run-ui-checks.mjs`.

---

## PART 10 — HACKATHON DEMONSTRATION (2-3 min)

1. **0:00** Open `/network`: hero + orb. Line: "AI screening only helps people who can reach screening." (10 s)
2. **0:15** Tap Saathi, grant mic (consent card shown). Say: "Mujhe apne gaon mein aankhon ki jaanch karwani hai." Saathi (spoken + transcript) asks for PIN.
3. **0:40** Say "four five three three three one". Saathi calls `find_camps`; cards appear with **SIMULATED** badge; Saathi says honestly these are demonstration camps.
4. **1:05** Tap a camp card → detail. Show verification legend and "price: not provided".
5. **1:20** Say/tap "Register interest": wizard opens prefilled; review screen; consent; confirm. Show receipt "Interest received — not an appointment".
6. **1:50** Switch to the health-worker session (real login, banner PROTOTYPE ACCOUNT): the request is in the list; mark "contacted"; show assisted registration with consent.
7. **2:15** Back as user: My DrishtiQ shows the status change (proves real backend state, not LLM talk).
8. **2:30** About page diagram: a real screening encounter would then use DrishtiQ AI + clinician review (existing module); unchanged, consent-based linking is future. Close on honesty slide: what is simulated vs planned.
Backup: if mic/Chrome STT fails → type the same lines; if Gemini quota out → rules mode (identical demo). Pre-seed and run `reset-demo` before presenting.

---

## PART 11 — RISKS AND OPEN QUESTIONS

| Risk | Impact | Mitigation |
|---|---|---|
| **Branch base / uncommitted redesign** (`router.ts`, `Shell.tsx`, `App.tsx` modified, redesign untracked files) | Network edits entangled with redesign; can lose work | **User chose "decide later"**: must be resolved at Phase 0. Recommendation: commit redesign on its own branch, then cut `feat/drishtiq-network` from it. No resets/stashes without consent |
| Free-tier quotas unknown (RPM/RPD not on pricing page) | Demo failure | rules fallback is first-class; read AI Studio limits before choosing model |
| Free-tier data used to improve Google products [V] | privacy | only anonymised non-personal text; PII scrub + unit test; never profile/registration data |
| Chrome STT is online and not on Firefox; Hindi TTS voices vary by device | voice experience variance | detect and degrade; test on the demo laptop/phone **before** the event |
| Hindi content accuracy | clinical misinformation | content flagged `illustrative` until reviewed; `docs/NETWORK_CONTENT_REVIEW.md` workflow; mirror existing "Hindi not clinically reviewed" precedent |
| Auth without verified identifiers | impersonation | identifier unverified by design; no personal-data release based on phone/email claims beyond own session; rate limits |
| `.gitignore` swallowing `*token*`, `*secret*`, `*credential*` names | files silently missing from commits | naming rule (Part 2.1) |
| No encryption at rest (same as clinical store) | data exposure on lost laptop | state in docs; minimal fields; purge; prod needs encrypted DB/disk (Plan C) |
| Demo data mistaken for real services | trust/ethics | simulated badge + ribbon + no real contacts + About table |
| Known clinical review-propagation issue | possible confusion | Network does not touch it; About page says nothing about clinical results |
| Bundle size / clinical regression | slower app | lazy-load `NetworkApp`; run existing suites each phase |
| Fonts: new woff2 must be local | offline test failure | self-host via fontsource, run `test_frontend_offline.py` |

### Open questions
**Blocking (needed at Phase 0):**
1. **Branch base** (see above). Plan assumes commit-then-branch unless told otherwise.

**Non-blocking, with recommendations:**
- Saathi persona gender/name styling → default feminine per brief; strings parameterised.
- Camp seed region → use Indore/Madhya Pradesh-area fictitious demo entries including PIN `453331` from your example; clearly simulated.
- Staff account creation → local CLI (no public signup for staff).
- Hindi reviewer available? → until then content marked "illustrative".
- Playwright adoption → optional; default is existing `node:test` runner.
- Gemini model choice → pick after checking AI Studio limits; id stays in config.

---

## PART 12 — RECOMMENDED FIRST IMPLEMENTATION PHASE

**Phase 1 (after Phase 0 branch step): "Network backbone + camp discovery slice".** Backend DB + seed + public camp/content APIs, and a minimal frontend slice proving routing and isolation.

Scope: `backend/network/{db,schema.sql,config,models,services/camps,services/content,routes/public,router}.py`, seed JSON, `app.py` hook, `requirements-app.txt`, `frontend/src/network/{NetworkApp,netRouter,NetworkShell(minimal),api}.tsx/ts`, router/App minimal hook, Devanagari font dep, camp search screen skeleton.

Objective acceptance criteria:
1. `GET /api/network/camps?pin=453331` returns seeded simulated camps, each with `verification:"simulated"`; `?pin=12` → 422 `invalid_pin`; unknown PIN → `[]` with explicit empty response.
2. Expired camps excluded by default, included with `include_expired=1`, and flagged.
3. `network.sqlite` is created only under the data dir; `cases.sqlite` byte-identical before/after test run.
4. Network router registered above the `/api/{path:path}` catch-all; all existing `/api/*` responses unchanged (existing `backend/test_api.py` and `tests/` pass as in the Phase 0 baseline).
5. Static test passes: nothing in `backend/network/**` references clinical tables or `state["db"]`.
6. `/network` renders inside `NetworkShell` (not clinical `Shell`); `/app/*` and `/` behave exactly as before; `npm run build` and `node tests/run-ui-checks.mjs` pass; no external URLs in build output.
7. Hindi strings render in Noto Sans Devanagari with `lang="hi"`; language toggle persists across reload.
8. No git commit, push or deploy performed; work only on `feat/drishtiq-network`.

## Verification (end-to-end, for any phase)
Backend: `.venv\Scripts\python -m pytest -q backend tests` (+ Network tests on the lightweight app). Frontend: `cd frontend && npm run build && node tests/run-ui-checks.mjs`. Manual: `start.bat`, walk the Part 10 demo path with mic and with typing; run `?axe=1` on each Network screen; test at 320 px and with reduced-motion enabled.

## Source notes (official docs fetched 2026-11-01)
Gemini pricing page (free-tier model list and "content used to improve our products" for free tier), rate-limits page (limits per project; values only visible in AI Studio), Live API docs (ephemeral tokens recommended for browsers; PCM 16 kHz in / 24 kHz out; free-tier availability and session limits **not stated** on the page fetched). Model names listed above come from that pricing page and must be re-checked at implementation time.
