// Theme generated from the single token source (design/tokens.json). The spacing, type, radius and shadow scales
// REPLACE Tailwind's defaults, so only approved values exist (e.g. p-5 does not compile).
import tokens from '../design/tokens.json' with { type: 'json' }

const px = (v) => `${v}px`
const c = tokens.color
const stage = Object.fromEntries(c.stage.map((s, i) => [String(i), s]))
const { $comment: _ignored, ...lesion } = c.lesion

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  corePlugins: { preflight: false }, // legacy screens rely on browser defaults; the design system has its own scoped reset
  theme: {
    spacing: { 0: '0px', px: '1px', ...Object.fromEntries(Object.entries(tokens.space).map(([k, v]) => [k, px(v)])) },
    fontFamily: { sans: tokens.font.family.split(',').map((s) => s.trim()), display: tokens.font.display.split(',').map((s) => s.trim()) },
    fontSize: {
      overline: [px(tokens.font.size.overline), { lineHeight: '1.25', letterSpacing: '0.06em' }],
      caption: [px(tokens.font.size.caption), { lineHeight: String(tokens.font.lineHeight.body) }],
      secondary: [px(tokens.font.size.secondary), { lineHeight: String(tokens.font.lineHeight.body) }],
      body: [px(tokens.font.size.body), { lineHeight: String(tokens.font.lineHeight.body) }],
      section: [px(tokens.font.size.section), { lineHeight: String(tokens.font.lineHeight.heading) }],
      page: [px(tokens.font.size.page), { lineHeight: String(tokens.font.lineHeight.heading) }],
      stage: [px(tokens.font.size.stage), { lineHeight: String(tokens.font.lineHeight.heading) }],
      lead: [px(tokens.font.size.lead), { lineHeight: '1.55' }],
      'display-sm': [px(tokens.font.size.displaySm), { lineHeight: '1.15' }],
      display: [px(tokens.font.size.display), { lineHeight: '1.08' }],
      'display-lg': [px(tokens.font.size.displayLg), { lineHeight: '1.04' }],
    },
    fontWeight: { normal: String(tokens.font.weight.regular), medium: String(tokens.font.weight.medium), semibold: String(tokens.font.weight.semibold) },
    borderRadius: { none: '0px', sm: '6px', control: px(tokens.radius.control), card: px(tokens.radius.card), xl: '24px', full: '9999px' },
    boxShadow: { none: 'none', overlay: tokens.shadow.overlay, card: tokens.shadow.card, lift: tokens.shadow.lift },
    colors: {
      transparent: 'transparent', current: 'currentColor', white: '#FFFFFF',
      neutral: c.neutral, brand: c.brand, text: c.text, surface: c.surface, border: c.border, focus: c.focus,
      stage, status: c.status, lesion, accent: c.accent, gradient: c.gradient,
    },
    extend: {
      height: { control: px(tokens.size.control), 'control-sm': px(tokens.size.controlCompact), topbar: px(tokens.size.topbar) },
      minHeight: { control: px(tokens.size.control) },
      width: { sidebar: px(tokens.size.sidebar), rail: px(tokens.size.rail) },
      maxWidth: { content: '1440px', measure: tokens.font.measure },
    },
  },
  plugins: [],
}
