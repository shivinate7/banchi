import { useEffect, useRef, useState, type ReactNode } from 'react'

import type { Place, SearchGroup } from './types'
import { PullConfirm } from './PullConfirm'
import { PositionBar } from './PositionBar'
import { PositionLabel } from './PositionLabel'
import { SearchField } from './SearchField'
import { CardLocations } from './CardLocations'
import { Button, EmptyState, Icon, Kbd, Notice, Pill, Segmented, Stat, type ButtonSize, type ButtonVariant, type IconName, type PillTone } from './kit'
import { ICON_NAMES } from './kit/Icon'
import './Gallery.css'

/* THE KIT — every primitive Banchi is built from, on one page, so the tokens are looked at
 * rather than only written. `make screenshot` renders it and `make design-check` measures the
 * Fulfillment floors here. Nothing is wired to a server.
 *
 * The four pull-confirm specimens keep their `data-specimen` names and their order:
 * app/tests/pull-confirm.spec.ts measures the vertical gaps between exactly those. */

const noop = () => {}

// ---------------------------------------------------------------------------- fixtures

function place(over: Partial<Place>): Place {
  return {
    label: 'Box 3 · Section 2 · Card 15',
    box: 3,
    index: 40,
    slot: 40,
    section: 2,
    card: 15,
    box_name: 'ME01 commons',
    section_start: 26,
    section_end: 50,
    box_total: 250,
    box_closed: true,
    fraction: 0.16,
    ...over,
  }
}

const CLOSED_BOX = place({})
const OPEN_BOX = place({ label: 'Box 7 · Section 1 · Card 12', box: 7, index: 12, section: 1, card: 12, box_name: null, section_start: 1, section_end: null, box_total: 62, box_closed: false, fraction: 12 / 62 })
const SINGLE_SECTION = place({ label: 'Box 9 · Section 1 · Card 4', box: 9, index: 4, section: 1, card: 4, box_name: 'Bulk, unsorted', section_start: 1, section_end: null, box_total: 80, box_closed: true, fraction: 0.05 })
const NO_FRACTION = place({ label: 'Box 4 · Section 1 · Card 1', box: 4, index: 1, section: 1, card: 1, box_name: null, section_start: 1, section_end: null, box_total: 0, box_closed: false, fraction: null })

const GROUP: SearchGroup = {
  sku: '8421991',
  names: ['Thievul'],
  number: '108',
  printed_total: '198',
  number_display: '108/198',
  set_hint: 'me01',
  condition: 'Near Mint',
  listed: { pushed: 0, staged: 1, live: 2 },
  on_hand: 3,
  cap: 4,
  listable: 3,
  copies: [
    { key: '3/40', state: 'identified', state_at: null, has_photo: true, place: CLOSED_BOX },
    { key: '7/12', state: 'identified', state_at: null, has_photo: true, place: OPEN_BOX },
    { key: '9/4', state: 'captured', state_at: null, has_photo: false, place: SINGLE_SECTION },
    { key: '4/1', state: 'sold', state_at: null, has_photo: true, place: NO_FRACTION },
  ],
}

const SECTIONS: readonly { id: string; label: string; group: string }[] = [
  { id: 'colour', label: 'Colour', group: 'Foundations' },
  { id: 'type', label: 'Type', group: 'Foundations' },
  { id: 'space', label: 'Space & radius', group: 'Foundations' },
  { id: 'elevation', label: 'Elevation', group: 'Foundations' },
  { id: 'motion', label: 'Motion', group: 'Foundations' },
  { id: 'icons', label: 'Icons', group: 'Foundations' },
  { id: 'buttons', label: 'Buttons', group: 'Primitives' },
  { id: 'kbd', label: 'Keycaps', group: 'Primitives' },
  { id: 'pills', label: 'Pills & dots', group: 'Primitives' },
  { id: 'fields', label: 'Fields', group: 'Primitives' },
  { id: 'segmented', label: 'Segmented & tabs', group: 'Primitives' },
  { id: 'notice', label: 'Notice', group: 'Primitives' },
  { id: 'receipt', label: 'Receipt & toast', group: 'Primitives' },
  { id: 'empty', label: 'Empty state', group: 'Primitives' },
  { id: 'skeleton', label: 'Skeleton & progress', group: 'Primitives' },
  { id: 'data', label: 'Data', group: 'Primitives' },
  { id: 'surfaces', label: 'Surfaces & menu', group: 'Primitives' },
  { id: 'pull-confirm', label: 'Pull-confirm', group: 'Screen pieces' },
  { id: 'position', label: 'Position bar', group: 'Screen pieces' },
  { id: 'position-label', label: 'Position label', group: 'Screen pieces' },
  { id: 'search', label: 'Search field', group: 'Screen pieces' },
  { id: 'locations', label: 'Card locations', group: 'Screen pieces' },
]

const COLOURS: readonly { name: string; token: string; ink?: boolean }[] = [
  { name: 'Page', token: '--bn-bg' },
  { name: 'Surface', token: '--bn-surface' },
  { name: 'Surface 2 · sunken', token: '--bn-surface-2' },
  { name: 'Surface 3 · hover', token: '--bn-surface-3' },
  { name: 'Ink', token: '--bn-ink', ink: true },
  { name: 'Ink 2', token: '--bn-ink-2', ink: true },
  { name: 'Ink 3', token: '--bn-ink-3', ink: true },
  { name: 'Ink 4', token: '--bn-ink-4', ink: true },
  { name: 'Line', token: '--bn-line' },
  { name: 'Line strong', token: '--bn-line-strong' },
  { name: 'Accent', token: '--bn-accent', ink: true },
  { name: 'Accent hover', token: '--bn-accent-hover', ink: true },
  { name: 'Accent press', token: '--bn-accent-press', ink: true },
  { name: 'Accent tint', token: '--bn-accent-tint' },
  { name: 'Live', token: '--bn-live', ink: true },
  { name: 'Live tint', token: '--bn-live-tint' },
  { name: 'OK', token: '--bn-ok', ink: true },
  { name: 'OK tint', token: '--bn-ok-tint' },
  { name: 'Warn', token: '--bn-warn', ink: true },
  { name: 'Warn tint', token: '--bn-warn-tint' },
  { name: 'Danger', token: '--bn-danger', ink: true },
  { name: 'Danger tint', token: '--bn-danger-tint' },
]

/* The text roles: one specimen each, named and labelled with the class that gives it. */
const TEXT_ROLES: readonly { cls: string; name: string; sample: string }[] = [
  { cls: 'bn-eyebrow', name: 'Eyebrow · mono caps', sample: 'Design system' },
  { cls: 'bn-label', name: 'Label · Inter caps', sample: 'This session' },
  { cls: 'bn-money', name: 'Money · tabular', sample: '$1,234.50' },
  { cls: 'bn-mono', name: 'Mono · machine strings', sample: '2026-09-02-box3-01' },
  { cls: 'bn-tnum', name: 'Tabular figures · Inter', sample: '1,625 cards · 443 SKUs' },
  { cls: 'bn-muted', name: 'Muted · ink-3', sample: 'Metadata and captions' },
  { cls: 'bn-faint', name: 'Faint · ink-4', sample: 'Disabled and dividers' },
]

const TYPE_SCALE: readonly { token: string; px: number; role: string }[] = [
  { token: '--bn-fs-5xl', px: 48, role: 'Home greeting' },
  { token: '--bn-fs-4xl', px: 36, role: 'Hero figure' },
  { token: '--bn-fs-3xl', px: 28, role: 'Page title' },
  { token: '--bn-fs-2xl', px: 22, role: 'Stat value · question' },
  { token: '--bn-fs-xl', px: 18, role: 'Section heading' },
  { token: '--bn-fs-lg', px: 16, role: 'Row primary' },
  { token: '--bn-fs-base', px: 14, role: 'Body' },
  { token: '--bn-fs-md', px: 13, role: 'Controls · table' },
  { token: '--bn-fs-sm', px: 12, role: 'Metadata' },
  { token: '--bn-fs-xs', px: 11, role: 'Label · pill' },
  { token: '--bn-fs-2xs', px: 10, role: 'Keycap · badge' },
]

const SPACES = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'] as const
const RADII = ['xs', 'sm', '', 'lg', 'xl', '2xl', 'full'] as const
const VARIANTS: readonly ButtonVariant[] = ['default', 'primary', 'ghost', 'quiet', 'danger', 'danger-solid', 'ok']
const SIZES: readonly ButtonSize[] = ['sm', 'md', 'lg', 'xl']
const TONES: readonly PillTone[] = ['default', 'accent', 'ok', 'warn', 'danger', 'live']

// ------------------------------------------------------------------------- scaffolding

function Section({ id, title, lede, children }: { id: string; title: string; lede?: ReactNode; children: ReactNode }) {
  return (
    <section className="kit-section" id={`kit-${id}`} data-kit-section={id}>
      <header className="kit-section-head">
        <h2 className="bn-section-title">{title}</h2>
        {lede ? <p className="kit-section-lede">{lede}</p> : null}
      </header>
      {children}
    </section>
  )
}

function Spec({ name, label, note, wide, forcePressed, children }: { name?: string; label: string; note?: ReactNode; wide?: boolean; forcePressed?: boolean; children: ReactNode }) {
  return (
    <div className={`kit-spec${wide ? ' kit-spec-wide' : ''}`} data-specimen={name} data-force-state={forcePressed ? 'pressed' : undefined}>
      <div className="kit-spec-label bn-label">{label}</div>
      <div className="kit-spec-body">{children}</div>
      {note ? <p className="kit-spec-note">{note}</p> : null}
    </div>
  )
}

function Code({ children }: { children: ReactNode }) {
  return <code className="kit-code">{children}</code>
}

function FieldSpecimen({ persona }: { persona: 'owner' | 'fulfiller' }) {
  const [text, setText] = useState(persona === 'owner' ? 'thievul' : '')
  return <SearchField value={text} onChange={setText} persona={persona} />
}

function MotionDemo({ duration, ease }: { duration: string; ease: string }) {
  const [tick, setTick] = useState(0)
  return (
    <button type="button" className="kit-motion" onClick={() => setTick((n) => n + 1)} title="Play">
      <span key={tick} className="kit-motion-dot" style={{ animationDuration: `var(${duration})`, animationTimingFunction: `var(${ease})` }} />
      <span className="kit-motion-label">
        <span className="bn-mono">{duration.replace('--bn-', '')}</span>
        <span className="bn-mono kit-motion-ease">{ease.replace('--bn-', '')}</span>
      </span>
      <Icon name="play" size={12} className="kit-motion-play" />
    </button>
  )
}

function useActiveSection(): string | null {
  const [active, setActive] = useState<string | null>(null)
  useEffect(() => {
    const nodes = Array.from(document.querySelectorAll<HTMLElement>('[data-kit-section]'))
    if (nodes.length === 0) return
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        const first = visible[0]
        if (first !== undefined) setActive((first.target as HTMLElement).dataset.kitSection ?? null)
      },
      { rootMargin: '-10% 0px -70% 0px', threshold: 0 },
    )
    for (const node of nodes) observer.observe(node)
    return () => observer.disconnect()
  }, [])
  return active
}

// -------------------------------------------------------------------------------- page

export function Gallery() {
  const active = useActiveSection()
  const scrolled = useRef(false)
  const jump = (id: string) => {
    scrolled.current = true
    document.getElementById(`kit-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  const groups = [...new Set(SECTIONS.map((s) => s.group))]

  return (
    <main className="gallery bn-page">
      <header className="bn-head kit-head">
        <div className="bn-head-text">
          <span className="bn-eyebrow">Design system</span>
          <h1 className="bn-title">
            <Icon name="grid" size={22} />
            Kit
          </h1>
          <p className="bn-lede">Every primitive the screens are built from, drawn from the tokens. Switch the theme in the nav to see both.</p>
        </div>
        <div className="bn-head-actions">
          <Pill tone="accent" mono>
            tokens.css
          </Pill>
          <Pill mono>kit.css</Pill>
          <Pill mono>kit/index.tsx</Pill>
        </div>
      </header>

      <div className="kit-layout">
        <nav className="kit-index" aria-label="Sections">
          {groups.map((group) => (
            <div key={group} className="kit-index-group">
              <div className="kit-index-label">{group}</div>
              {SECTIONS.filter((s) => s.group === group).map((s) => (
                <button key={s.id} type="button" className="kit-index-link" aria-current={active === s.id ? 'true' : undefined} onClick={() => jump(s.id)}>
                  {s.label}
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="kit-sections">
          {/* ------------------------------------------------------------ foundations */}
          <Section id="colour" title="Colour" lede="Three registers: ink is what you read, line is what separates, brand is where to look. Indigo for action, vermilion for what is live.">
            <div className="kit-swatches">
              {COLOURS.map((c) => (
                <div key={c.token} className="kit-swatch">
                  <span className="kit-swatch-chip" style={{ background: `var(${c.token})` }}>
                    {c.ink ? <span className="kit-swatch-sample" style={{ color: 'var(--bn-surface)' }}>Aa</span> : null}
                  </span>
                  <span className="kit-swatch-name">{c.name}</span>
                  <span className="kit-swatch-token bn-mono">{c.token}</span>
                </div>
              ))}
            </div>
          </Section>

          <Section id="type" title="Type" lede={<>Manrope for headings and big figures, Inter for everything, JetBrains Mono only for machine strings. Numbers in tables are Inter with <Code>tabular-nums</Code>.</>}>
            <div className="kit-faces">
              <div className="kit-face" style={{ fontFamily: 'var(--bn-font-display)', fontWeight: 800 }}>
                <span>Manrope</span>
                <span className="kit-face-role">display · headings, figures</span>
              </div>
              <div className="kit-face" style={{ fontFamily: 'var(--bn-font-ui)', fontWeight: 600 }}>
                <span>Inter</span>
                <span className="kit-face-role">ui · everything</span>
              </div>
              <div className="kit-face" style={{ fontFamily: 'var(--bn-font-mono)', fontWeight: 500 }}>
                <span>JetBrains Mono</span>
                <span className="kit-face-role">mono · SKUs, run names, codes, kbd</span>
              </div>
            </div>
            <div className="kit-type">
              {TYPE_SCALE.map((t) => (
                <div key={t.token} className="kit-type-row">
                  <span className="kit-type-meta">
                    <span className="bn-mono">{t.token.replace('--bn-fs-', '')}</span>
                    <span className="bn-mono kit-type-px">{t.px}px</span>
                    <span className="kit-type-role">{t.role}</span>
                  </span>
                  <span className="kit-type-sample" style={{ fontSize: `var(${t.token})`, fontFamily: t.px >= 22 ? 'var(--bn-font-display)' : 'var(--bn-font-ui)', fontWeight: t.px >= 22 ? 800 : t.px >= 16 ? 600 : 500 }}>
                    Every card has an address
                  </span>
                </div>
              ))}
            </div>
            <div className="kit-roles">
              {TEXT_ROLES.map((role) => (
                <div key={role.cls} className="kit-role">
                  <span className={`kit-role-sample ${role.cls}`}>{role.sample}</span>
                  <span className="kit-role-name">{role.name}</span>
                  <span className="kit-role-token bn-mono">.{role.cls}</span>
                </div>
              ))}
            </div>
          </Section>

          <Section id="space" title="Space & radius" lede="A 4px scale, and radii from 4px to a pill.">
            <div className="kit-spaces">
              {SPACES.map((s) => (
                <div key={s} className="kit-space">
                  <span className="kit-space-bar" style={{ width: `var(--bn-${s})` }} />
                  <span className="bn-mono kit-space-name">--bn-{s}</span>
                </div>
              ))}
            </div>
            <div className="kit-radii">
              {RADII.map((r) => (
                <div key={r || 'r'} className="kit-radius">
                  <span className="kit-radius-box" style={{ borderRadius: `var(--bn-r${r ? `-${r}` : ''})` }} />
                  <span className="bn-mono">--bn-r{r ? `-${r}` : ''}</span>
                </div>
              ))}
            </div>
          </Section>

          <Section id="elevation" title="Elevation" lede="Three shadows and an accent glow. Panels sit at 1, hover and dialogs rise.">
            <div className="kit-shadows">
              {['--bn-shadow-1', '--bn-shadow-2', '--bn-shadow-3', '--bn-shadow-accent'].map((s) => (
                <div key={s} className="kit-shadow" style={{ boxShadow: `var(${s})` }}>
                  <span className="bn-mono">{s.replace('--bn-', '')}</span>
                </div>
              ))}
            </div>
          </Section>

          <Section id="motion" title="Motion" lede="Three durations, three curves. Press a tile to play it. Everything the operator causes should be visible; reduced motion collapses all of it.">
            <div className="kit-motions">
              {['--bn-t-fast', '--bn-t', '--bn-t-slow'].map((d) =>
                ['--bn-ease', '--bn-ease-out', '--bn-ease-spring'].map((e) => <MotionDemo key={d + e} duration={d} ease={e} />),
              )}
            </div>
          </Section>

          <Section id="icons" title="Icons" lede={<>{ICON_NAMES.length} names on a 24 grid, 1.75 stroke, round joins. Never inline an <Code>&lt;svg&gt;</Code> in a screen — add a path here.</>}>
            <div className="kit-icons">
              {ICON_NAMES.map((name: IconName) => (
                <div key={name} className="kit-icon">
                  <Icon name={name} size={20} />
                  <span className="bn-mono">{name}</span>
                </div>
              ))}
            </div>
          </Section>

          {/* -------------------------------------------------------------- primitives */}
          <Section id="buttons" title="Buttons" lede="Seven variants, four sizes. Primary is the one thing to do; danger is red; money moments carry the figure in the label.">
            <div className="kit-grid">
              {VARIANTS.map((v) => (
                <Spec key={v} label={v}>
                  <div className="kit-row kit-row-wrap">
                    {SIZES.map((s) => (
                      <Button key={s} variant={v} size={s}>
                        {s}
                      </Button>
                    ))}
                  </div>
                  <div className="kit-row kit-row-wrap">
                    <Button variant={v} icon="check">
                      Icon
                    </Button>
                    <Button variant={v} kbd="S">
                      Key
                    </Button>
                    <Button variant={v} iconRight="arrowRight">
                      Right
                    </Button>
                    <Button variant={v} disabled>
                      Disabled
                    </Button>
                    <Button variant={v} busy>
                      Busy
                    </Button>
                  </div>
                </Spec>
              ))}
              <Spec label="shapes">
                <div className="kit-row kit-row-wrap">
                  <Button pill icon="camera">
                    Pill
                  </Button>
                  <Button variant="primary" pill>
                    Primary pill
                  </Button>
                  <Button iconOnly icon="refresh">
                    Reload
                  </Button>
                  <Button iconOnly variant="ghost" icon="x">
                    Close
                  </Button>
                  <Button iconOnly variant="primary" size="lg" icon="plus">
                    Add
                  </Button>
                </div>
                <Button variant="primary" block icon="dollar">
                  Push 12 listings · $184.20
                </Button>
              </Spec>
            </div>
          </Section>

          <Section id="kbd" title="Keycaps" lede="An hour in the review queue is a keyboard, so every choice shows its key. Hidden on coarse pointers.">
            <div className="kit-grid">
              <Spec label="kbd">
                <div className="kit-row kit-row-wrap">
                  <Kbd>1</Kbd>
                  <Kbd>S</Kbd>
                  <Kbd>Esc</Kbd>
                  <Kbd>↵</Kbd>
                  <span className="bn-kbd-group">
                    <Kbd>⌘</Kbd>
                    <Kbd>K</Kbd>
                  </span>
                  <span className="bn-kbd-group">
                    <Kbd>,</Kbd>
                    <Kbd>Q</Kbd>
                  </span>
                </div>
              </Spec>
              <Spec label="in a button · on accent">
                <div className="kit-row kit-row-wrap">
                  <Button kbd="R" icon="refresh">
                    Reload
                  </Button>
                  <Button variant="primary" kbd="↵">
                    Answer all 16
                  </Button>
                  <Button variant="quiet" kbd="X" icon="x">
                    Close
                  </Button>
                </div>
              </Spec>
              <Spec label="row keycap · 28px" note={<>The review queue's row keycap — <Code>.review-key</Code>, a candidate for promotion.</>}>
                <div className="kit-row">
                  <kbd className="kit-keycap">1</kbd>
                  <kbd className="kit-keycap">2</kbd>
                  <kbd className="kit-keycap">3</kbd>
                  <kbd className="kit-keycap kit-keycap-blank">–</kbd>
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="pills" title="Pills & dots" lede="Status in six tones. Live is vermilion and pulses.">
            <div className="kit-grid">
              <Spec label="tones">
                <div className="kit-row kit-row-wrap">
                  {TONES.map((t) => (
                    <Pill key={t} tone={t}>
                      {t}
                    </Pill>
                  ))}
                </div>
              </Spec>
              <Spec label="with icon · mono · outline">
                <div className="kit-row kit-row-wrap">
                  <Pill tone="ok" icon="check">
                    reconciled
                  </Pill>
                  <Pill tone="live" icon="dot">
                    live
                  </Pill>
                  <Pill tone="accent" mono>
                    SKU 8608000
                  </Pill>
                  <Pill outline>outline</Pill>
                  <Pill tone="warn" outline>
                    parked
                  </Pill>
                </div>
              </Spec>
              <Spec label="dots">
                <div className="kit-row kit-row-wrap">
                  <span className="bn-dot" /> default
                  <span className="bn-dot bn-dot-ok" /> ok
                  <span className="bn-dot bn-dot-warn" /> warn
                  <span className="bn-dot bn-dot-danger" /> danger
                  <span className="bn-dot bn-dot-accent" /> accent
                  <span className="bn-dot bn-dot-live" /> live
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="fields" title="Fields" lede="34px controls, 40px large. Focus is the accent ring, product-wide.">
            <div className="kit-grid">
              <Spec label="input · with hint">
                <label className="bn-field">
                  <span className="bn-field-label">Box name</span>
                  <input className="bn-input" defaultValue="RB Epics" />
                  <span className="bn-field-hint">Names are unique; case is folded.</span>
                </label>
              </Spec>
              <Spec label="input-wrap · icon and key">
                <span className="bn-input-wrap">
                  <Icon name="search" size={16} />
                  <input className="bn-input" placeholder="Find a card" />
                  <Kbd>/</Kbd>
                </span>
              </Spec>
              <Spec label="select · textarea">
                <select className="bn-select" defaultValue="market">
                  <option value="market">Market price</option>
                  <option value="low">Lowest listing</option>
                </select>
                <textarea className="bn-textarea" defaultValue="Held back: bullish above $5." />
              </Spec>
              <Spec label="large · mono · disabled">
                <input className="bn-input bn-input-lg" placeholder="Type the name of the card" />
                <input className="bn-input bn-input-mono" defaultValue="2026-09-02-box6-01" />
                <input className="bn-input" defaultValue="Disabled" disabled />
              </Spec>
              <Spec label="checks">
                <div className="kit-row kit-row-wrap">
                  <label className="bn-check">
                    <input type="checkbox" defaultChecked /> Listed only
                  </label>
                  <label className="bn-check">
                    <input type="checkbox" /> Split by game
                  </label>
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="segmented" title="Segmented & tabs" lede="Segmented for a mode; tabs for a view.">
            <div className="kit-grid">
              <Spec label="segmented">
                <Segmented
                  value="boxes"
                  onChange={noop}
                  options={[
                    { value: 'boxes', label: 'Boxes', icon: 'box' },
                    { value: 'cards', label: 'Cards', icon: 'layers' },
                    { value: 'pull', label: 'Pull', icon: 'hand', kbd: 'P' },
                  ]}
                  label="Mode"
                />
              </Spec>
              <Spec label="tabs">
                <div className="bn-tabs">
                  <button type="button" className="bn-tab" aria-selected="true">
                    <Icon name="inbox" size={14} /> Review <Pill tone="warn">12</Pill>
                  </button>
                  <button type="button" className="bn-tab">
                    <Icon name="flag" size={14} /> Parked <Pill>6</Pill>
                  </button>
                  <button type="button" className="bn-tab">
                    <Icon name="history" size={14} /> Answered
                  </button>
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="notice" title="Notice" lede="Four tones; the code line is where the machine string goes.">
            <div className="kit-grid">
              <Spec label="info">
                <Notice title="The export is fetched to a scope this process names">Every card of this game carries a set hint, so the scope is one set.</Notice>
              </Spec>
              <Spec label="warn">
                <Notice tone="warn" title="Two runs are joined but neither is emitted">
                  Emit them together, so the live cap is spent once.
                </Notice>
              </Spec>
              <Spec label="danger · with code">
                <Notice tone="danger" title="The answer was refused" code="sku_not_a_candidate · Box 2 · Section 1 · Card 14">
                  The queue file was rewritten after this screen read it. Reload to see the rows the route will take.
                </Notice>
              </Spec>
              <Spec label="ok">
                <Notice tone="ok" title="Reconciled">
                  405 SKUs read a live count for the first time.
                </Notice>
              </Spec>
            </div>
          </Section>

          <Section id="receipt" title="Receipt & toast" lede="A receipt is an undo anchored beside the thing it undoes, draining over its window. A toast is the same shape, floating.">
            <div className="kit-grid">
              <Spec label="receipt · draining" wide>
                <div className="bn-receipt" style={{ ['--receipt-ms' as string]: '20000ms' }}>
                  <Icon name="check" size={16} style={{ color: 'var(--bn-ok)' }} />
                  <span className="bn-grow">
                    <strong>Answered as Near Mint Holofoil</strong>
                    <span className="bn-mono" style={{ display: 'block', fontSize: 11, opacity: 0.65 }}>
                      Box 2 · Section 1 · Card 14
                    </span>
                  </span>
                  <span className="bn-receipt-bar" />
                  <Button size="sm" icon="undo" kbd="U">
                    Undo
                  </Button>
                </div>
              </Spec>
              <Spec label="toast · receipt / ok / refusal" wide>
                <div className="kit-toasts">
                  <div className="bn-toast bn-toast-receipt">
                    <Icon name="undo" size={16} className="bn-toast-icon" />
                    <div className="bn-toast-text">
                      <div className="bn-toast-title">Marked sold</div>
                      <div className="bn-toast-body">Box 3 · Section 2 · Card 15</div>
                    </div>
                    <button type="button" className="bn-toast-action">
                      Undo <kbd className="bn-kbd">U</kbd>
                    </button>
                  </div>
                  <div className="bn-toast bn-toast-ok">
                    <Icon name="check" size={16} className="bn-toast-icon" />
                    <div className="bn-toast-text">
                      <div className="bn-toast-title">Import file written</div>
                      <div className="bn-toast-body">437 copies · one file</div>
                    </div>
                  </div>
                  <div className="bn-toast bn-toast-refusal">
                    <Icon name="alert" size={16} className="bn-toast-icon" />
                    <div className="bn-toast-text">
                      <div className="bn-toast-title">The store is busy behind a running join</div>
                      <div className="bn-toast-body">store_busy</div>
                    </div>
                  </div>
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="empty" title="Empty state" lede="A real sentence and one way onward. At zero it should feel like a reward.">
            <div className="kit-grid">
              <Spec label="empty" wide>
                <div className="bn-panel">
                  <EmptyState
                    icon="check"
                    title="All caught up."
                    body="You answered 16 cards in 4 min 12 s · 2 closed."
                    actions={
                      <>
                        <Button variant="primary" icon="tag" iconRight="arrowRight">
                          Price the answers
                        </Button>
                        <Button icon="play">Run another box</Button>
                      </>
                    }
                  />
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="skeleton" title="Skeleton & progress" lede="Reserve the shape while the server answers; move the bar when the operator does.">
            <div className="kit-grid">
              <Spec label="skeleton">
                <div className="bn-skeleton" style={{ height: 22, width: '60%' }} />
                <div className="bn-skeleton" style={{ height: 14, width: '40%' }} />
                <div className="bn-skeleton" style={{ height: 56 }} />
                <div className="bn-skeleton" style={{ height: 56 }} />
              </Spec>
              <Spec label="progress · default and ok">
                <div className="bn-progress">
                  <span style={{ width: '34%' }} />
                </div>
                <div className="bn-progress bn-progress-ok">
                  <span style={{ width: '100%' }} />
                </div>
                <div className="kit-row">
                  <Stat value="16" label="answered" />
                  <Stat value="$184" label="to list" />
                  <Stat value="2" label="closed" />
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="data" title="Data" lede="Key/value pairs, a table, list rows. Numbers right-aligned and tabular.">
            <div className="kit-grid">
              <Spec label="kv">
                <dl className="bn-kv">
                  <dt>Card</dt>
                  <dd>Snorlax</dd>
                  <dt>Number</dt>
                  <dd className="bn-mono">014/132</dd>
                  <dt>Market</dt>
                  <dd className="bn-money">$84.50</dd>
                  <dt>Confidence</dt>
                  <dd>High</dd>
                </dl>
              </Spec>
              <Spec label="table" wide>
                <div className="bn-panel">
                  <table className="bn-table">
                    <thead>
                      <tr>
                        <th>Card</th>
                        <th>Condition</th>
                        <th>SKU</th>
                        <th className="num">Market</th>
                        <th className="num">Copies</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        ['Snorlax', 'Near Mint Holofoil', '8608002', '143.65', 1],
                        ['Charizard ex', 'Near Mint', '8607411', '12.00', 3],
                        ['Bidoof', 'Near Mint', '8601230', '0.12', 14],
                      ].map(([name, cond, sku, market, n]) => (
                        <tr key={String(sku)}>
                          <td>{name}</td>
                          <td>{cond}</td>
                          <td className="bn-mono">{sku}</td>
                          <td className="num">${market}</td>
                          <td className="num">{n}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Spec>
              <Spec label="list rows">
                <div className="bn-panel bn-list">
                  <button type="button" className="bn-list-row">
                    <Icon name="box" size={16} /> <span className="bn-grow">Box 3 · RB Epics</span> <Pill>723</Pill>
                  </button>
                  <button type="button" className="bn-list-row" aria-current="true">
                    <Icon name="box" size={16} /> <span className="bn-grow">Box 4 · WB1 R2</span> <Pill tone="accent">56</Pill>
                  </button>
                  <button type="button" className="bn-list-row">
                    <Icon name="box" size={16} /> <span className="bn-grow">Box 5 · UNL BBOX C/UC 1</span> <Pill>105</Pill>
                  </button>
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="surfaces" title="Surfaces & menu" lede="A panel is raised, a well is sunken, a menu pops.">
            <div className="kit-grid">
              <Spec label="panel · head and body">
                <div className="bn-panel">
                  <div className="bn-panel-head">
                    <span className="bn-section-title">
                      <Icon name="history" size={16} /> Recent runs
                    </span>
                    <Button size="sm" variant="ghost" iconRight="arrowRight">
                      All runs
                    </Button>
                  </div>
                  <div className="bn-panel-body">Body text sits at 14px on the surface.</div>
                </div>
              </Spec>
              <Spec label="well · rule">
                <div className="bn-well">A sunken well for code or an inactive track.</div>
                <div className="bn-rule">or</div>
                <div className="bn-well bn-mono">banchi emit runs/2026-09-02-box6-01</div>
              </Spec>
              <Spec label="menu">
                <div className="bn-menu kit-menu-inline">
                  <div className="bn-menu-label">Box</div>
                  <button type="button" className="bn-menu-item">
                    <Icon name="divider" size={16} /> Put in a divider <Kbd>S</Kbd>
                  </button>
                  <button type="button" className="bn-menu-item">
                    <Icon name="tag" size={16} /> Set hint <Kbd>H</Kbd>
                  </button>
                  <div className="bn-menu-sep" />
                  <button type="button" className="bn-menu-item bn-menu-item-danger">
                    <Icon name="trash" size={16} /> Delete this box
                  </button>
                </div>
              </Spec>
            </div>
          </Section>

          {/* ------------------------------------------------------------ screen pieces */}
          <Section id="pull-confirm" title="Pull-confirm" lede="The one solid fill the Fulfiller ever sees. Three states, and the owner-side key hint.">
            <div className="kit-stack kit-stack-narrow">
              <Spec name="default" label="default · the Fulfillment case">
                <PullConfirm label="Pull this card" onConfirm={noop} />
              </Spec>
              <Spec name="pressed" label="pressed" forcePressed>
                <PullConfirm label="Pull this card" onConfirm={noop} />
              </Spec>
              <Spec name="disabled" label="disabled" note="Never appears in the Fulfillment view; that view has no disabled state.">
                <PullConfirm label="Pull this card" onConfirm={noop} disabled />
              </Spec>
              <Spec name="with-key" label="default + key hint · owner-side only">
                <PullConfirm label="Pull this card" onConfirm={noop} keyHint="↵" />
              </Spec>
            </div>
          </Section>

          <Section id="position" title="Position bar" lede={<>How far into its box a card sits. A closed box earns a percentage; an open one says <Code>so far</Code>.</>}>
            <div className="kit-stack">
              <Spec name="bar-closed" label="closed box · 250 cards">
                <PositionBar place={CLOSED_BOX} />
              </Spec>
              <Spec name="bar-open" label="open box · the denominator still moves">
                <PositionBar place={OPEN_BOX} />
              </Spec>
              <Spec name="bar-single" label="one section · no dividers declared">
                <PositionBar place={SINGLE_SECTION} />
              </Spec>
              <Spec name="bar-unknown" label="no fraction · the server declined to say">
                <PositionBar place={NO_FRACTION} />
              </Spec>
              <Spec name="bar-fulfiller" label="the Fulfiller's density">
                <PositionBar place={CLOSED_BOX} persona="fulfiller" />
              </Spec>
            </div>
          </Section>

          <Section id="position-label" title="Position label" lede="One ranking, three flows: stacked, slot-led for a column, and run for a sentence.">
            <div className="kit-grid">
              <Spec label="stack · path-led">
                <div className="kit-poslabel" style={{ ['--pos-slot' as string]: '32px' }}>
                  <PositionLabel label="Box 3 · Section 2 · Card 15" />
                </div>
              </Spec>
              <Spec label="stack · slot-led">
                <div className="kit-poslabel" style={{ ['--pos-slot' as string]: '32px' }}>
                  <PositionLabel label="Box 3 · Section 2 · Card 15" lead="slot" />
                </div>
              </Spec>
              <Spec label="run · in a sentence">
                <p style={{ ['--pos-slot' as string]: '16px' }}>
                  The card is still at <PositionLabel label="Box 3 · Section 2 · Card 15" flow="run" />.
                </p>
              </Spec>
              <Spec label="departed">
                <div className="kit-poslabel" style={{ ['--pos-slot' as string]: '32px' }}>
                  <PositionLabel label="Box 3 · departed · B3 #31" />
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="search" title="Search field" lede="The owner's carries a / hotkey and its chip; the Fulfiller's carries neither and keeps a visible label.">
            <div className="kit-stack">
              <Spec name="search-owner" label="owner · dense, with the key chip">
                <FieldSpecimen persona="owner" />
              </Spec>
              <Spec name="search-fulfiller" label="fulfiller · large, no keys">
                <FieldSpecimen persona="fulfiller" />
              </Spec>
            </div>
          </Section>

          <Section id="locations" title="Card locations" lede="One card, four copies, one sold. Same group, same actions; the prop that differs is the persona.">
            <div className="kit-stack">
              <Spec name="locations-owner" label="owner · a bar on every row">
                <CardLocations group={GROUP} persona="owner" onSell={noop} busyKey={null} soldKeys={new Set()} />
              </Spec>
              <Spec name="locations-fulfiller" label="fulfiller · every copy is its own card" note="Photographs resolve against the capture server; without one each copy draws its missing-photo sentence, which is a real state.">
                <CardLocations group={GROUP} persona="fulfiller" onSell={noop} busyKey={null} soldKeys={new Set()} />
              </Spec>
            </div>
          </Section>
        </div>
      </div>
    </main>
  )
}
