import { useEffect, useId, useRef, useState } from 'react'
import type { ButtonHTMLAttributes, CSSProperties, ReactNode, Ref } from 'react'
import { Icon, type IconName } from './Icon'
import { rememberTheme, storedTheme, type Theme } from '../deviceMemory'
import {
  CARD, DISPLAY_BRACKET, DISPLAY_CAPS, HOLO, HOLO_RECT,
  SHEEN_HEIGHT, SMALL_BRACKET, SMALL_STROKE, TILE,
} from './markGeometry'
import { DEFAULT_VARIANT, MARKS, SHEEN, type LogoVariant } from './markPalettes'

export { Icon }
export type { IconName }

/* ---- Button ------------------------------------------------------------------ */
export type ButtonVariant = 'default' | 'primary' | 'ghost' | 'quiet' | 'danger' | 'danger-solid' | 'ok'
export type ButtonSize = 'sm' | 'md' | 'lg' | 'xl'

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  readonly ref?: Ref<HTMLButtonElement>
  readonly variant?: ButtonVariant
  readonly size?: ButtonSize
  readonly icon?: IconName
  readonly iconRight?: IconName
  readonly kbd?: string
  readonly busy?: boolean
  readonly block?: boolean
  readonly pill?: boolean
  readonly iconOnly?: boolean
}

export function Button({
  variant = 'default',
  size = 'md',
  icon,
  iconRight,
  kbd,
  busy,
  block,
  pill,
  iconOnly,
  className,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  const classes = [
    'bn-btn',
    variant !== 'default' ? `bn-btn-${variant}` : '',
    size !== 'md' ? `bn-btn-${size}` : '',
    block ? 'bn-btn-block' : '',
    pill ? 'bn-btn-pill' : '',
    iconOnly ? 'bn-btn-icon' : '',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ')
  return (
    <button type={type} className={classes} data-busy={busy ? 'true' : undefined} {...rest}>
      {icon ? <Icon name={icon} size={size === 'sm' ? 14 : size === 'xl' ? 20 : 16} /> : null}
      {iconOnly ? <span className="bn-sr">{children}</span> : children}
      {iconRight ? <Icon name={iconRight} size={size === 'sm' ? 14 : 16} /> : null}
      {kbd ? <Kbd>{kbd}</Kbd> : null}
    </button>
  )
}

/* ---- IconButton ---------------------------------------------------------------
   THE ONE ICON-ONLY BUTTON (owner's ruling, 2026-09-24, ICONOGRAPHY; D-icon-buttons;
   `docs/specs/iconography.md`): a common, repeated action from the vocabulary — Mark sold,
   Undo, Retire, Edit, Delete, Copy, Download, Open, Close, Filter, Sort, and the rest the
   spec names — becomes an icon with a `label` that is REQUIRED: an icon with no word is a
   guess, not a control. A press that spends money or cannot be undone (Send, Identify, Stand
   down) keeps its words and stays a plain `Button`. `kit-adoption`'s `R2-icon-only-button`
   rule refuses the shapes a screen reaches for instead — `iconOnly` on `Button`, a hand-rolled
   `<button>`/`<svg>`, or a worded `Button` whose label is a vocabulary verb — outside this
   file, so every icon action in the product goes through here.

   TWO NESTED BOXES, ON PURPOSE. The outer `<button>` is the HIT AREA: `min-width`/
   `min-height: 40px` always, at every `size` (D117's thumb floor, made a floor this control
   never drops under, rather than the breakpoint-raised `--btn-h` every other kit control
   reads). The inner `.bn-icon-face` is the VISUAL face — 28px at `size="md"`, the density a
   packed row like a walk or a table needs — and carries the hover/pressed/danger paint, so
   the paint stays small while the target stays reachable. Reuses `button`'s own D50
   cursor/response/press floors for free (a bare-tag selector in base.css).

   `label` is BOTH the tooltip text and, when `name` is not given, the accessible name. `name`
   is for a row where every instance would otherwise announce the same word — "Undo the sale
   at Section 2, Card 5" as `name`, "Undo" as the short `label` a tooltip has room for. The
   tooltip (`.bn-icon-tip`, kit.css) is `position: absolute` off `.bn-btn`'s own `position:
   relative`, so showing it never moves anything else (D118). It shows on real `:hover`, on
   `:focus-visible` (never a mouse `:focus`, so a click does not leave it stuck open), and on
   a touch long-press (`onTouchStart` past `LONG_PRESS_MS`, cleared on release) — the phone
   width has no hover, and a Banchi-specific glyph needs its word somewhere reachable there
   too. It is `aria-hidden`: the accessible name is the button's own `aria-label`, never the
   tooltip's text, so a screen reader is never told the label twice.

   `pressed` marks a toggle of one act (Hold/Release, Reveal/Hide) with `aria-pressed`, tinted
   like `Chip`'s own pressed state — change the label AND the icon together on a toggle, never
   the icon alone (D118). `badge` draws a small count at the corner, `aria-hidden` and
   `pointer-events: none`, so its arrival moves nothing (D118). */
const LONG_PRESS_MS = 500
const FACE_PX: Record<ButtonSize, number> = { sm: 24, md: 28, lg: 34, xl: 40 }
const GLYPH_PX: Record<ButtonSize, number> = { sm: 12, md: 14, lg: 16, xl: 18 }

export type IconButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children' | 'aria-label' | 'title'> & {
  readonly ref?: Ref<HTMLButtonElement>
  readonly icon: IconName
  /** The tooltip text, and the accessible name unless `name` overrides it. Required. */
  readonly label: string
  /** A longer accessible name for a row where `label` alone would repeat on every instance
   *  ("Undo the sale at Section 2, Card 5"). The tooltip still shows the short `label`. */
  readonly name?: string
  readonly size?: ButtonSize
  /** The one variant this takes: everything that is not a danger press stays the kit's
   *  default icon-only look (ghost), which is what every icon-only close/reload button in the
   *  product already draws. */
  readonly tone?: 'danger'
  readonly busy?: boolean
  /** A toggle of one act: Hold vs. Release, Reveal vs. Hide. Change the label and the icon
   *  together with it, never the icon alone (D118). */
  readonly pressed?: boolean
  /** A small count at the corner — a filter bar's active-facet count. Never moves the layout
   *  (D118): it is `position: absolute`, drawn outside the flow. */
  readonly badge?: number | string
  /** A keycap, shown inside the tooltip beside the label, never on the button itself — an
   *  icon-only control has no room to spare for one. */
  readonly kbd?: string
}

export function IconButton({
  icon,
  label,
  name,
  size = 'md',
  tone,
  busy,
  pressed,
  badge,
  kbd,
  className,
  type = 'button',
  onTouchStart,
  onTouchEnd,
  onTouchCancel,
  ...rest
}: IconButtonProps) {
  const [longPress, setLongPress] = useState(false)
  const timer = useRef<number | null>(null)
  const clearTimer = () => {
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = null
  }
  const classes = ['bn-btn', 'bn-icon-btn', className ?? ''].filter(Boolean).join(' ')
  return (
    <button
      type={type}
      className={classes}
      aria-label={name ?? label}
      aria-pressed={pressed}
      data-tone={tone}
      data-busy={busy ? 'true' : undefined}
      data-tip-open={longPress ? 'true' : undefined}
      onTouchStart={(event) => {
        clearTimer()
        timer.current = window.setTimeout(() => setLongPress(true), LONG_PRESS_MS)
        onTouchStart?.(event)
      }}
      onTouchEnd={(event) => {
        clearTimer()
        setLongPress(false)
        onTouchEnd?.(event)
      }}
      onTouchCancel={(event) => {
        clearTimer()
        setLongPress(false)
        onTouchCancel?.(event)
      }}
      {...rest}
    >
      <span className="bn-icon-face" style={{ width: FACE_PX[size], height: FACE_PX[size] }}>
        <Icon name={icon} size={GLYPH_PX[size]} />
      </span>
      {badge !== undefined && badge !== 0 && badge !== '' ? (
        <span className="bn-icon-count" aria-hidden="true">
          {badge}
        </span>
      ) : null}
      <span className="bn-icon-tip" aria-hidden="true">
        {label}
        {kbd ? <Kbd>{kbd}</Kbd> : null}
      </span>
    </button>
  )
}

/* ---- Kbd ------------------------------------------------------------------------ */
export function Kbd({ children, className }: { readonly children: ReactNode; readonly className?: string }) {
  return (
    <kbd className={['bn-kbd', className].filter(Boolean).join(' ')} aria-hidden="true">
      {children}
    </kbd>
  )
}

/* ---- KeyHint ---------------------------------------------------------------------- */
/** A PHRASE THAT NAMES KEYS, as one unit: "<KeyHint>Press <Kbd>,</Kbd> then a letter to jump</KeyHint>".
 *  On a touch screen the whole phrase hides, so no sentence is left with a hole where its key
 *  was (UX-040). A bare `Kbd` in running text never hides by itself: wrap the phrase instead. */
export function KeyHint({ children, className }: { readonly children: ReactNode; readonly className?: string }) {
  return <span className={['bn-keyhint', className].filter(Boolean).join(' ')}>{children}</span>
}

/* ---- Pill ------------------------------------------------------------------------- */
export type PillTone = 'default' | 'accent' | 'ok' | 'warn' | 'danger' | 'live'
export function Pill({
  tone = 'default',
  size = 'md',
  icon,
  mono,
  outline,
  className,
  children,
}: {
  readonly tone?: PillTone
  /** `sm` (18px) is the pill inside a button, a tab or a dense row. */
  readonly size?: 'sm' | 'md'
  readonly icon?: IconName
  readonly mono?: boolean
  readonly outline?: boolean
  readonly className?: string
  readonly children: ReactNode
}) {
  const classes = [
    'bn-pill',
    tone !== 'default' ? `bn-pill-${tone}` : '',
    size === 'sm' ? 'bn-pill-sm' : '',
    mono ? 'bn-pill-mono' : '',
    outline ? 'bn-pill-outline' : '',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ')
  return (
    <span className={classes}>
      {icon ? <Icon name={icon} size={size === 'sm' ? 10 : 12} /> : null}
      {children}
    </span>
  )
}

/* ---- Chip ---------------------------------------------------------------------------- */
/** A toggle chip: choose one of a set, filter a list. `pressed` draws the ink fill; `count`
 *  draws the figure in its own badge; `dot` puts a tone dot before the label. */
export type ChipProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  readonly ref?: Ref<HTMLButtonElement>
  readonly pressed?: boolean
  readonly icon?: IconName
  readonly count?: number | string
  readonly dot?: 'default' | 'ok' | 'warn' | 'danger' | 'live' | 'accent'
}
export function Chip({ pressed, icon, count, dot, className, children, type = 'button', ...rest }: ChipProps) {
  return (
    <button type={type} className={['bn-chip', className].filter(Boolean).join(' ')} aria-pressed={pressed === undefined ? undefined : pressed} {...rest}>
      {dot ? <span className={dot === 'default' ? 'bn-dot' : `bn-dot bn-dot-${dot}`} /> : null}
      {icon ? <Icon name={icon} size={14} /> : null}
      {children}
      {count !== undefined ? <span className="bn-chip-count">{count}</span> : null}
    </button>
  )
}

/* ---- Page header ------------------------------------------------------------------ */
export function PageHeader({
  title,
  icon,
  lede,
  actions,
  className,
}: {
  readonly title: ReactNode
  readonly icon?: IconName
  readonly lede?: ReactNode
  readonly actions?: ReactNode
  readonly className?: string
}) {
  return (
    <header className={['bn-head', className].filter(Boolean).join(' ')}>
      <div className="bn-head-text">
        <h1 className="bn-title">
          {icon ? <Icon name={icon} size={22} /> : null}
          {title}
        </h1>
        {lede ? <p className="bn-lede">{lede}</p> : null}
      </div>
      {actions ? <div className="bn-head-actions">{actions}</div> : null}
    </header>
  )
}

/* ---- Empty state -------------------------------------------------------------------- */
export function EmptyState({
  icon = 'sparkles',
  title,
  body,
  actions,
  className,
}: {
  readonly icon?: IconName
  readonly title: ReactNode
  readonly body?: ReactNode
  readonly actions?: ReactNode
  readonly className?: string
}) {
  return (
    <div className={['bn-empty', className].filter(Boolean).join(' ')}>
      <div className="bn-empty-art">
        <Icon name={icon} size={24} />
      </div>
      <p className="bn-empty-title">{title}</p>
      {body ? <p className="bn-empty-body">{body}</p> : null}
      {actions ? <div className="bn-empty-actions">{actions}</div> : null}
    </div>
  )
}

/* ---- Notice ---------------------------------------------------------------------------- */
/** A refusal, a warning, a standing condition. The sentence is the person's; the machine's own
 *  words — the `code`, and any server text with a path or a command in it (`detail`) — sit
 *  behind "What the server said", closed by default (D-notice-detail, amends D196). They are
 *  one press away for a bug report and never in plain view (UX-038).
 *
 *  `compact` draws one line that fits `StatusSlot`, and the disclosure opens OVER the page, so
 *  the answer to a press moves nothing below it (D118). `action` is one control beside the
 *  sentence: a retry, a way forward. */
export function Notice({
  tone = 'info',
  title,
  code,
  detail,
  action,
  compact,
  children,
  className,
}: {
  readonly tone?: 'info' | 'warn' | 'danger' | 'ok'
  readonly title?: ReactNode
  readonly code?: string
  readonly detail?: ReactNode
  readonly action?: ReactNode
  readonly compact?: boolean
  readonly children?: ReactNode
  readonly className?: string
}) {
  const icon: IconName = tone === 'danger' ? 'alert' : tone === 'warn' ? 'alert' : tone === 'ok' ? 'check' : 'info'
  const said = code || detail
  return (
    <div
      className={['bn-notice', tone !== 'info' ? `bn-notice-${tone}` : '', compact ? 'bn-notice-compact' : '', className ?? ''].filter(Boolean).join(' ')}
      role={tone === 'danger' ? 'alert' : 'status'}
    >
      <Icon name={icon} size={16} />
      <div className="bn-notice-text">
        {title ? <div className="bn-notice-title">{title}</div> : null}
        {children ? <div className="bn-notice-body">{children}</div> : null}
      </div>
      {said ? (
        <details className="bn-notice-said">
          <summary>What the server said</summary>
          <div className="bn-notice-said-body">
            {detail ? <div>{detail}</div> : null}
            {code ? <code className="bn-notice-code">{code}</code> : null}
          </div>
        </details>
      ) : null}
      {action ? <div className="bn-notice-action">{action}</div> : null}
    </div>
  )
}

/* ---- Refusal and Retry ------------------------------------------------------------------- */
/* TWO SHAPES FOR "THAT DID NOT WORK", AND THEY ARE NOT THE SAME THING (UX-041). A REFUSAL is a
   permanent "no" from this place: it says it cannot be done here and offers no retry, because
   pressing again gets the same answer. A RETRY is a failure that may pass: it offers "Try again",
   and the button shows that it is trying. Both draw next to the control that caused them. */

/** It cannot be done here. One sentence, and a way forward if there is one. Never a retry. */
export function Refusal({
  title,
  children,
  code,
  detail,
  action,
  compact,
  className,
}: {
  readonly title: ReactNode
  readonly children?: ReactNode
  readonly code?: string
  readonly detail?: ReactNode
  /** A way FORWARD (another screen, another press), never the same press again. */
  readonly action?: ReactNode
  readonly compact?: boolean
  readonly className?: string
}) {
  return (
    <Notice tone="warn" title={title} code={code} detail={detail} action={action} compact={compact} className={['bn-refusal', className].filter(Boolean).join(' ')}>
      {children}
    </Notice>
  )
}

/** It failed and may pass on a second try. "Try again" spins while it tries and keeps its size. */
export function Retry({
  title,
  children,
  code,
  detail,
  onRetry,
  busy,
  retryLabel = 'Try again',
  compact,
  className,
}: {
  readonly title: ReactNode
  readonly children?: ReactNode
  readonly code?: string
  readonly detail?: ReactNode
  readonly onRetry: () => void
  readonly busy?: boolean
  readonly retryLabel?: string
  readonly compact?: boolean
  readonly className?: string
}) {
  return (
    <Notice
      tone="danger"
      title={title}
      code={code}
      detail={detail}
      compact={compact}
      className={['bn-retry', className].filter(Boolean).join(' ')}
      action={
        <Button size="sm" icon="refresh" busy={busy} disabled={busy} aria-busy={busy ? 'true' : undefined} onClick={onRetry}>
          {retryLabel}
        </Button>
      }
    >
      {children}
    </Notice>
  )
}

/** The shape `server.ts:describeFailure` says a failure is: a refusal or a retry. The server's
 *  own text is NEVER the title (D196, D-notice-detail): the title is a plain sentence, the one
 *  passed, or a default that says only whether trying again can help. The server's words and its
 *  code sit behind "What the server said". */
export function FailureNotice({
  failure,
  title,
  onRetry,
  busy,
  compact,
}: {
  readonly failure: { readonly code: string; readonly message: string; readonly kind?: 'refusal' | 'retry' }
  readonly title?: ReactNode
  readonly onRetry?: () => void
  readonly busy?: boolean
  readonly compact?: boolean
}) {
  if (failure.kind === 'retry' && onRetry !== undefined) {
    return (
      <Retry title={title ?? 'That did not go through.'} code={failure.code} detail={failure.message} onRetry={onRetry} busy={busy} compact={compact} />
    )
  }
  return <Refusal title={title ?? 'That cannot be done here.'} code={failure.code} detail={failure.message} compact={compact} />
}

/* ---- Reload ---------------------------------------------------------------------------------- */
/** THE ONE RELOAD CONTROL (UX-056): one place (the page's actions), one label, one key, one busy
 *  state. It spins and refuses a second press while the read is in flight, and `R` presses it
 *  from anywhere on the page that is not a field. `hotkey={false}` for a second one on a page. */
export function ReloadButton({
  onReload,
  busy,
  label = 'Reload',
  hotkey = true,
  className,
}: {
  readonly onReload: () => void
  readonly busy?: boolean
  readonly label?: string
  readonly hotkey?: boolean
  readonly className?: string
}) {
  const latest = useRef({ onReload, busy })
  useEffect(() => {
    latest.current = { onReload, busy }
  })
  useEffect(() => {
    if (!hotkey) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'r' && event.key !== 'R') return
      if (event.metaKey || event.ctrlKey || event.altKey || event.defaultPrevented) return
      const target = event.target
      if (target instanceof HTMLElement && (target.isContentEditable || target.closest('input, textarea, select') !== null)) return
      if (document.querySelector('[aria-modal="true"]') !== null) return
      if (latest.current.busy) return
      event.preventDefault()
      latest.current.onReload()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [hotkey])
  return (
    <IconButton
      icon="refresh"
      label={label}
      kbd={hotkey ? 'R' : undefined}
      busy={busy}
      disabled={busy}
      aria-busy={busy ? 'true' : undefined}
      onClick={onReload}
      className={['bn-reload', className].filter(Boolean).join(' ')}
    />
  )
}

/* ---- Segmented ---------------------------------------------------------------------------- */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  size,
  className,
}: {
  readonly value: T
  readonly options: readonly { readonly value: T; readonly label: ReactNode; readonly icon?: IconName; readonly kbd?: string }[]
  readonly onChange: (next: T) => void
  readonly label?: string
  /** `'sm'` matches a 28px row of search/select controls (S10) — see kit.css's own note on
   *  why this is two same-weight classes, container and item, never a descendant selector. */
  readonly size?: 'sm'
  readonly className?: string
}) {
  return (
    <div className={['bn-seg', size === 'sm' ? 'bn-seg-sm' : '', className].filter(Boolean).join(' ')} role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={['bn-seg-item', size === 'sm' ? 'bn-seg-item-sm' : ''].filter(Boolean).join(' ')}
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.icon ? <Icon name={option.icon} size={14} /> : null}
          {option.label}
          {option.kbd ? <Kbd>{option.kbd}</Kbd> : null}
        </button>
      ))}
    </div>
  )
}

/* ---- Stat ------------------------------------------------------------------------------------ */
export function Stat({
  value,
  label,
  size,
  className,
}: {
  readonly value: ReactNode
  readonly label: ReactNode
  /** `'sm'` reads at Orders' own 14:11 (`.orders-index-figure`); `'xs'` reads at Inventory's
   *  own 11:11, un-bolded (`.browse-boxcell-count` beside `.browse-boxcell-meta`) (S9). The
   *  base size (omitted) is unchanged at 22:12. */
  readonly size?: 'sm' | 'xs'
  readonly className?: string
}) {
  return (
    <div className={['bn-stat', size ? `bn-stat-${size}` : '', className].filter(Boolean).join(' ')}>
      <span className="bn-stat-value">{value}</span>
      <span className="bn-stat-label">{label}</span>
    </div>
  )
}

/* ---- Logo --------------------------------------------------------------------------------------- */
export { Lockup } from './Lockup'
export type { LogoVariant }
export { VARIANTS } from './markPalettes'

/** The Banchi mark. `docs/specs/logo.md` is the state of record and `scripts/build-mark.mjs`
 *  generates the geometry and the palettes out of that spec's own generator — neither is
 *  hand-written here, and `make docs-audit`'s `logo parity` row reconciles the palettes against
 *  section 9 in both directions.
 *
 *  TWO OPTICAL CUTS, PICKED BY SIZE (section 3, swept in section 11). Below 64px the taper is
 *  removed and the stroke thickens, because a 1.7 stroke is a scratch at 32px and absent at 16px;
 *  the marbling goes too, because at these sizes it loses to a flat prism gradient. Every call
 *  site in this app is below 64px, so the small cut is what ships and `DISPLAY` is what
 *  `#/gallery` shows.
 *
 *  FIXED DARK IN BOTH THEMES, ON PURPOSE (section 12). The placeholder this replaced was drawn in
 *  `--bn-ink` on `--bn-bg` and so inverted with the theme. The mark is an object rather than an
 *  ink color — an app icon does not invert when the phone does — and a light ground was derived
 *  and lost: a near-white tile on a near-white page has no silhouette at any size this app draws.
 *
 *  `aria-hidden`, always. Every call site names itself on the wrapper. */
export function Logo({
  size = 28,
  variant = DEFAULT_VARIANT,
  className,
}: {
  readonly size?: number
  readonly variant?: LogoVariant
  readonly className?: string
}) {
  // Per instance, because the sidebar, the mobile drawer and a crash page can all be mounted at
  // once and each mark's gradients are referenced by id. The sheet gets away with a module
  // counter; a component cannot, and two marks sharing `url(#bk)` is silent — both references
  // resolve, to the first one's gradient.
  const id = useId().replace(/:/g, '')
  const mark = MARKS[variant]
  const small = size < 64

  const bracket = small ? (
    <path
      d={SMALL_BRACKET}
      fill="none"
      stroke={`url(#${id}b)`}
      strokeWidth={SMALL_STROKE}
      strokeLinecap="round"
    />
  ) : (
    <>
      <path d={DISPLAY_BRACKET} fill={`url(#${id}b)`} />
      {DISPLAY_CAPS.map(([cx, cy, r]) => (
        <circle key={`${cx},${cy}`} cx={cx} cy={cy} r={r} fill={`url(#${id}b)`} />
      ))}
    </>
  )

  return (
    <svg className={className} width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
      <defs>
        <linearGradient id={`${id}g`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={mark.ground[0]} />
          <stop offset="1" stopColor={mark.ground[1]} />
        </linearGradient>
        <linearGradient id={`${id}b`} x1=".75" y1=".067" x2=".25" y2=".933">
          {mark.bracket.map((c, i) => (
            <stop key={c + i} offset={[0, 0.33, 0.67, 1][i]} stopColor={c} />
          ))}
        </linearGradient>
        <linearGradient id={`${id}s`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFFFFF" stopOpacity={SHEEN} />
          <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
        </linearGradient>
        <linearGradient id={`${id}p`} x1=".671" y1=".030" x2=".329" y2=".970">
          {mark.prism.map((c, i) => (
            <stop key={c + i} offset={i / 4} stopColor={c} />
          ))}
        </linearGradient>
        <clipPath id={`${id}t`}>
          <path d={TILE} />
        </clipPath>
        {!small && (
          <>
            <filter id={`${id}f`} x="-30%" y="-30%" width="160%" height="160%">
              <feTurbulence
                type="fractalNoise"
                baseFrequency={HOLO.baseFrequency}
                numOctaves={HOLO.octaves}
                seed={HOLO.seed}
                result="t"
              />
              <feDisplacementMap
                in="SourceGraphic"
                in2="t"
                scale={HOLO.displacement}
                xChannelSelector="R"
                yChannelSelector="G"
              />
            </filter>
            <clipPath id={`${id}c`}>
              <rect x={CARD.x} y={CARD.y} width={CARD.w} height={CARD.h} rx={CARD.r} />
            </clipPath>
          </>
        )}
      </defs>

      <path d={TILE} fill={`url(#${id}g)`} />
      <g clipPath={`url(#${id}t)`}>
        <rect width="100" height={SHEEN_HEIGHT} fill={`url(#${id}s)`} />
      </g>
      {bracket}
      <g transform="rotate(180 50 50)">{bracket}</g>
      <rect x={CARD.x} y={CARD.y} width={CARD.w} height={CARD.h} rx={CARD.r} fill={mark.base} />
      {small ? (
        <rect x={CARD.x} y={CARD.y} width={CARD.w} height={CARD.h} rx={CARD.r} fill={`url(#${id}p)`} />
      ) : (
        <g clipPath={`url(#${id}c)`} filter={`url(#${id}f)`}>
          <rect
            x={HOLO_RECT.x}
            y={HOLO_RECT.y}
            width={HOLO_RECT.w}
            height={HOLO_RECT.h}
            fill={`url(#${id}p)`}
          />
        </g>
      )}
    </svg>
  )
}

/* ---- Leave ---------------------------------------------------------------------------------------- */
/** Keeps an overlay mounted for one beat after `open` turns false, with `leaving` true, so the
 *  kit's `[data-leaving]` animation can run before the node goes. Render while `mounted`;
 *  put `data-leaving={leaving ? 'true' : undefined}` on the scrim and the sheet/dialog. */
export function useLeave(open: boolean, ms = 140): { readonly mounted: boolean; readonly leaving: boolean } {
  const [mounted, setMounted] = useState(open)
  const [leaving, setLeaving] = useState(false)
  const was = useRef(open)
  useEffect(() => {
    if (open) {
      was.current = true
      setMounted(true)
      setLeaving(false)
      return
    }
    if (!was.current) return
    was.current = false
    setLeaving(true)
    const timer = window.setTimeout(() => {
      setMounted(false)
      setLeaving(false)
    }, ms)
    return () => window.clearTimeout(timer)
  }, [open, ms])
  return { mounted, leaving }
}

/* ---- Crop --------------------------------------------------------------------------------------- */
/* A RIG PHOTOGRAPH IS MOSTLY STAND, and every screen that draws one small has the same problem:
   the card sits at [126, 741, 1770, 3038] inside a 2160x3840 frame, so nearly a fifth of the
   height above it is bracket and desk. `POST /pipeline/crop-preview` returns the rectangle the
   pipeline's own detector found, and this is the arithmetic that turns that rectangle into a
   picture of the card. It is here rather than on a screen because it was written twice — the
   Home hero and the Pricing thumbnails — and the maths is the half that is subtly wrong in
   silence. WHAT IS NOT HERE is the fetching: the hero asks once for one card, the worklist asks
   for the rows a scroll brings into view, and those are policies, not geometry. */
export type Crop = {
  readonly frame: readonly [number, number]
  readonly rect: readonly [number, number, number, number]
}

/** Scale the photograph so the card's WIDTH fills its window, and put `focus` — a share of the
 *  card's own height — at the window's centre. The window is usually squarer than a card, so
 *  only part of the height can show, and `focus` chooses which part: 0.5 centres the card,
 *  lower rides up towards the art and the name. The offsets are percentages of the image's own
 *  box, which is what a percentage `translate` resolves against, so no pixel size is needed.
 *  Returns `undefined` for no crop, which leaves the element's own framing alone: a refusal
 *  must never be worse than no request at all. Pair it with `.bn-crop` (kit.css). */
export function cropStyle(crop: Crop | null, focus = 0.34): CSSProperties | undefined {
  if (crop === null) return undefined
  const [fw, fh] = crop.frame
  const [x, y, rw, rh] = crop.rect
  if (fw <= 0 || fh <= 0 || rw <= 0 || rh <= 0) return undefined
  const dx = ((x + rw / 2) / fw - 0.5) * 100
  const dy = ((y + rh * focus) / fh - 0.5) * 100
  return {
    width: `${(fw / rw) * 100}%`,
    transform: `translate(calc(-50% - ${dx.toFixed(3)}%), calc(-50% - ${dy.toFixed(3)}%))`,
  }
}

/* ---- Theme --------------------------------------------------------------------------------------
   THE STORAGE ITSELF IS IN `deviceMemory.ts`, WHICH IS THE ONE FILE THIS APP KEEPS BROWSER
   PREFERENCES IN — the argument for keeping it there, and the eslint exception that makes it
   the only place, are both written at the top of that file. */
export type { Theme } from '../deviceMemory'

export function readTheme(): Theme {
  return storedTheme() ?? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
}

export function applyTheme(theme: Theme): void {
  if (theme === 'dark') document.documentElement.setAttribute('data-theme', 'dark')
  else document.documentElement.removeAttribute('data-theme')
  rememberTheme(theme)
}

/* ---- the page scaffold and the overlays ----------------------------------------------------
   Every screen imports these from here and never from the files behind them, so one import line
   is how a new screen inherits every other screen's frame (D-one-page-width). */
export { Page, PageRouteContext, usePageRoute, Verdict, Toolbar, StatusSlot, Loading, Section } from './Page'
export type { PageProps, PageRoute } from './Page'
export { Sheet, Modal, Popover, ConfirmSheet, SheetHost, useFocusTrap, useReturnFocus, useOverlayLayer, overlayOpen, useInOverlay } from './overlay'
export type { OverlayLayerOptions } from './overlay'

/* ---- the data primitives and the sheet registry (kit-data) ---------------------------------
   Screens import these from here, never from `./data` or `./sheets` directly. */
export {
  Money, Count, FilterCount, Select, FilterChips, SortControl, StatusBadge, STATUS_TONES, CardLine, CardThumb, BoxLabel, Sep,
  ProductLink, OrderLink, Location, boxesMostRecentFirst,
} from './data'
export type {
  BoxRecency, StatusKind, StatusTone, CardThumbSize, PickOption, FilterFacet, FilterValue, SortOption, SortValue,
} from './data'
export { registerSheet, openSheet, closeSheet, useOpenSheet, sheetHref, hasSheet } from './sheets'
export type { SheetProps, SheetKind, OpenSheet, SheetHostProps } from './sheets'
export { matchQuery } from './match'

/* ---- the filter bar, and the URL view state it is built to sit in (kit-filtering) -----------
   Screens import these from here too, never from `./filters` or `./viewState` directly. */
export { FilterBar, HideToggle, SortHeader } from './filters'
export type { FilterBarProps, FilterBarSearch, FilterBarSort, FilterBarHide, FilterBarCount } from './filters'
export { countFacets, filterRows, withCounts } from './facets'
export type { FacetValueOf } from './facets'
export { Highlight, matchSpans } from './highlight'
export type { HighlightKind } from './highlight'
export { useViewQuery, patchViewQuery, useViewParam, useViewFlag, useFacetParams, useSortParam } from './viewState'
