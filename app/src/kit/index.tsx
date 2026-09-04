import { useEffect, useRef, useState } from 'react'
import type { ButtonHTMLAttributes, CSSProperties, ReactNode, Ref } from 'react'
import { Icon, type IconName } from './Icon'
import { rememberTheme, storedTheme, type Theme } from '../deviceMemory'

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

/* ---- Kbd ------------------------------------------------------------------------ */
export function Kbd({ children, className }: { readonly children: ReactNode; readonly className?: string }) {
  return (
    <kbd className={['bn-kbd', className].filter(Boolean).join(' ')} aria-hidden="true">
      {children}
    </kbd>
  )
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
  eyebrow,
  title,
  icon,
  lede,
  actions,
  className,
}: {
  readonly eyebrow?: ReactNode
  readonly title: ReactNode
  readonly icon?: IconName
  readonly lede?: ReactNode
  readonly actions?: ReactNode
  readonly className?: string
}) {
  return (
    <header className={['bn-head', className].filter(Boolean).join(' ')}>
      <div className="bn-head-text">
        {eyebrow ? <span className="bn-eyebrow">{eyebrow}</span> : null}
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
export function Notice({
  tone = 'info',
  title,
  code,
  children,
  className,
}: {
  readonly tone?: 'info' | 'warn' | 'danger' | 'ok'
  readonly title?: ReactNode
  readonly code?: string
  readonly children?: ReactNode
  readonly className?: string
}) {
  const icon: IconName = tone === 'danger' ? 'alert' : tone === 'warn' ? 'alert' : tone === 'ok' ? 'check' : 'info'
  return (
    <div className={['bn-notice', tone !== 'info' ? `bn-notice-${tone}` : '', className ?? ''].filter(Boolean).join(' ')} role={tone === 'danger' ? 'alert' : 'status'}>
      <Icon name={icon} size={16} />
      <div className="bn-stack" style={{ gap: 2 }}>
        {title ? <div className="bn-notice-title">{title}</div> : null}
        {children ? <div>{children}</div> : null}
        {code ? <div className="bn-notice-code">{code}</div> : null}
      </div>
    </div>
  )
}

/* ---- Segmented ---------------------------------------------------------------------------- */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  className,
}: {
  readonly value: T
  readonly options: readonly { readonly value: T; readonly label: ReactNode; readonly icon?: IconName; readonly kbd?: string }[]
  readonly onChange: (next: T) => void
  readonly label?: string
  readonly className?: string
}) {
  return (
    <div className={['bn-seg', className].filter(Boolean).join(' ')} role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className="bn-seg-item"
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
export function Stat({ value, label, className }: { readonly value: ReactNode; readonly label: ReactNode; readonly className?: string }) {
  return (
    <div className={['bn-stat', className].filter(Boolean).join(' ')}>
      <span className="bn-stat-value">{value}</span>
      <span className="bn-stat-label">{label}</span>
    </div>
  )
}

/* ---- Logo --------------------------------------------------------------------------------------- */
export function Logo({ size = 28, className }: { readonly size?: number; readonly className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="16" fill="var(--bn-ink)" />
      <path
        d="M20 16h13.5c7 0 11.5 3.6 11.5 9.4 0 3.9-2.2 6.7-5.4 7.9 4.3 1 7.4 4.3 7.4 9 0 6.4-5 10.7-12.7 10.7H20V16zm12.6 13.6c3.5 0 5.6-1.8 5.6-4.6s-2.1-4.5-5.6-4.5h-5.8v9.1h5.8zm1.1 18.9c3.9 0 6.2-2 6.2-5.2s-2.3-5.1-6.2-5.1h-6.9v10.3h6.9z"
        fill="var(--bn-bg)"
      />
      <circle cx="47" cy="17" r="5" fill="var(--bn-live)" />
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
