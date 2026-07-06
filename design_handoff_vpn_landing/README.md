# Handoff: VPN Landing Page — Cyberpunk "Hacker Terminal" Redesign

## Overview
Redesign of the VPN sales landing page (currently at `http://84.247.166.53/`) in a cyberpunk / hacker-terminal aesthetic. Goal: modernize the look and increase perceived trust/urgency for a crypto-paid VPN subscription product, targeting a tech-savvy, privacy-conscious Russian-speaking audience.

## About the Design Files
The file `design-reference-2a.dc.html` in this folder is a **design reference built in HTML** — a static prototype showing the intended look, layout, copy, and color system. It is **not production code to copy directly**. Your task is to **recreate this design in the target codebase's existing environment** (plain HTML/CSS, or whatever framework the site currently uses) using its established build/deploy setup — or, if this is a fresh build, plain semantic HTML/CSS is sufficient; no JS framework is required since the current site has no interactive app logic beyond payment links.

Open `design-reference-2a.dc.html` directly in a browser to see it live — it is self-contained (single file). See also `screenshot-2a-full.png` for a static reference image of the target card layout (note: the screenshot is a fixed-width preview card, ~400px design width — the real site should be built responsive/full-width, see Responsive Behavior below).

## Fidelity
**High-fidelity.** Colors, typography, spacing, and copy in the reference file are final — recreate pixel-close. Exact hex values and font stacks are listed below.

## Screens / Views
Single-page landing page, one long scroll, sections top to bottom:

### 1. Terminal window header (bash chrome)
- Fake "terminal window" bar: 3 traffic-light dots (red `#ff2b4d`, yellow `#ffd60a`, green `#00ff41`), 9×9px circles, `border-radius:50%`, `gap:6px`
- Right-aligned label text: `vpn-router — bash — 80×24`, font `Share Tech Mono`, 11px, color `rgba(0,255,65,.5)`
- Padding 14px 22px, bottom border `1px solid rgba(0,255,65,.3)`
- Background: near-black `#050705` with a faint green grid texture — two linear-gradients (1px lines every 22px) at `rgba(0,255,65,.03)`, one horizontal one vertical (subtle CRT/grid feel), applied to the whole page background

### 2. Fake system log
- Monospace log lines (font `Share Tech Mono`, 12px, line-height 1.7), simulating a terminal boot sequence:
  - `root@core:~$ nmap -sV target.net` — dim green `rgba(0,255,65,.45)`
  - `[+] host up 0.014s latency` — cyan `#00d4ff` (with dim green sub-text for the latency figure)
  - `[+] 443/tcp open encrypted` — cyan `#00d4ff` ("open" in bright green `#00ff41`)
  - `[!] traffic obfuscation ENABLED` — red `#ff2b4d` ("ENABLED" in bright green)
  - `root@core:~$ ./vpn_router --start` — dim green
- Purely decorative/atmospheric; not real data.

### 3. Hero headline + CTA
- Headline: "БЫСТРЫЙ_VPN / _ДОСТУП" — font `Rajdhani` (fallback) — actually rendered in monospace-styled heavy weight, 27px, line-height 1.3, bright green `#00ff41`, `text-shadow: 0 0 10px rgba(0,255,65,.6)` (neon glow). A small blinking-cursor block (12×22px solid green rectangle) sits after the text — implement as a CSS `blink` keyframe animation (this reference is static; add `@keyframes blink { 50% { opacity: 0 } }` at ~1s interval for the real build)
- Subhead: `// YouTube · Telegram · Instagram · ChatGPT` / `// подключение — 60 сек., без логов` — 12px, line-height 1.8, `rgba(0,255,65,.55)`
- CTA button: `$ выбрать_тариф --run` — solid bright green `#00ff41` background, near-black text `#020402`, bold 13px, padding 12px 22px, glow shadow `0 0 18px rgba(0,255,65,.45)`. On hover: brighten (`filter: brightness(1.25)`), intensify glow to `0 0 26px`.

### 4. Pricing tariffs (3 cards, stacked)
Each is a flex row: label left, price right, padding 12px 14px, font 12px.
- **1 месяц — 200₽**: border `1px solid rgba(0,212,255,.35)`, background `rgba(0,212,255,.05)`, label prefix `[01]` in cyan `#00d4ff`
- **3 месяца — 500₽** ("// выгоднее" badge inline, muted): border `1px solid #ffd60a` (yellow), background `rgba(255,214,10,.08)`, label prefix `[03]` in yellow
- **6 месяцев — 900₽** ("// лучший" badge inline, muted): border `1px solid #ff2b4d` (red), background `rgba(255,43,77,.08)`, label prefix `[06]` in red
- All prices in white `#fff`, bold.
- Each card should be clickable → links to the corresponding payment flow (see current site: "Оплатить" per tariff).

### 5. How-it-works (3 steps)
Numbered list, 12px, line-height 2, dim green text with colored step numbers matching the tariff colors (cyan/yellow/red — purely visual rhythm, no functional link to tariffs):
1. Оплата криптовалютой
2. Установка v2rayN / v2rayNG / Hiddify
3. Ссылка после подтверждения

### 6. Status bar (footer strip)
- Top border: dashed `1px rgba(0,255,65,.25)`
- Text 11px, dim green `rgba(0,255,65,.35)`: `STATUS: CONNECTED · UPTIME 99.98% · ENCRYPTION AES-256`
- Purely decorative trust signal.

## Interactions & Behavior
- Tariff cards and the main CTA are clickable, linking to payment (same flow as current site — crypto payment, then link delivered after confirmation).
- Blinking cursor next to the headline (CSS animation, ~1s step interval) — the only motion on the page; keep everything else static (no scroll animations) to preserve the "terminal" feel and keep it fast/lightweight.
- Hover states: CTA and tariff rows brighten/glow slightly on hover (see colors above). No other hover states needed.
- No modals, no multi-step forms — this mirrors the current site's simple structure (pick tariff → pay → receive link).

## State Management
None needed — static marketing page. If tariff selection is tracked (e.g. to prefill a payment provider), a single selected-tariff value is sufficient; no other client state.

## Design Tokens

**Colors**
- Background: `#050705` (near-black, slightly green-tinted)
- Bright green (primary/brand): `#00ff41`
- Dim green (secondary text): `rgba(0,255,65,.45–.55)` / muted labels `rgba(0,255,65,.3–.35)`
- Cyan (accent 1): `#00d4ff`
- Yellow (accent 2): `#ffd60a`
- Red (accent 3): `#ff2b4d`
- White: `#fff` (prices, emphasis)
- Grid texture overlay: `rgba(0,255,65,.03)`, 22px repeat, both axes

**Typography**
- Font family: `'Share Tech Mono', monospace` for all body/log/label text; headline can stay in the same monospace stack (no separate display font is required for this variant — everything is intentionally monospace for the "terminal" feel)
- Sizes used: 10px (micro-labels), 11px (status/footer), 12px (body/log/steps), 13px (buttons), 27px (headline)
- Weights: 400 regular for log/body, 700–800 bold for headline and CTA

**Spacing**
- Card/section horizontal padding: 22px
- Vertical rhythm between blocks: 18–24px
- Tariff row internal padding: 12px 14px, 8px gap between rows

**Borders / Radius**
- No border radius anywhere (sharp corners throughout — intentional for the terminal aesthetic)
- Borders: 1px solid, colored per accent (cyan/yellow/red), or `rgba(0,255,65,.25–.3)` dashed for the footer divider

**Shadows / Glow**
- Headline: `text-shadow: 0 0 10px rgba(0,255,65,.6)`
- CTA button: `box-shadow: 0 0 18px rgba(0,255,65,.45)`, brightens on hover

## Responsive Behavior
The reference file is a fixed ~400px preview card (design-tool artifact). For the real site:
- Build fluid/full-width, centering the same content column at a comfortable reading width (~480–560px) on desktop, full-bleed padding on mobile.
- Maintain minimum tap target height of 44px on tariff rows and CTA for mobile.
- All colors, spacing ratios, and copy carry over unchanged — only the outer container width and padding should adapt.

## Assets
No image assets — everything is CSS (gradients, box-shadows, text). Font loaded from Google Fonts: `Share Tech Mono` (https://fonts.googleapis.com/css2?family=Share+Tech+Mono).

## Files
- `design-reference-2a.dc.html` — self-contained HTML reference, open directly in a browser (contains this one design plus earlier exploration variants below it in the same scrollable page — only the "2a" card, near the top, is in scope for this handoff)
- `screenshot-2a-full.png` — static image of the target card for quick reference without opening the HTML
