import { createContext, useContext, useEffect, useId } from 'react'
import type { HTMLAttributes, ReactNode } from 'react'
import { Icon, type IconName } from './Icon'
import { useInOverlay } from './overlay'

/* THE PAGE SCAFFOLD. Every screen is built from this from now on (D272).
 *
 * The owner's durability rule, 2026-09-23: a new page in the sidebar inherits the properties
 * of the other pages without being told. So the things every page shares live here, once:
 * one width (`--bn-page-w`, fluid below it), one top gap (`--bn-page-top`), one left edge
 * (D197), one h1, one place for the verdict, one toolbar that folds as a unit, one status
 * slot that holds its space (D118), one loading shape and one empty state. The page is a
 * query container named `bn-page`, so a screen's tiers follow the column it was given
 * rather than the window — 720 in a desktop window with the rail is a different column
 * from 720 on a phone, and only the column knows which.
 *
 * A NEW SCREEN IS ONE `ROUTES` ENTRY PLUS A VIEW THAT RETURNS `<Page>`. The shell wraps each
 * view in `PageRouteContext`, so the title defaults to the route's own `title ?? label`. */

/** What the shell knows about the route a view is drawn for. `persona`, added for
 *  D288: the Fulfiller's route is the one place the ICONOGRAPHY rule does not
 *  apply (`docs/specs/iconography.md` section 2, rule 1) — `OverlayFrame`'s Close reads it
 *  to decide word or icon, since a Sheet or Modal is portalled and cannot tell from its own
 *  DOM position which persona is looking at it. */
export type PageRoute = {
  readonly path: string
  readonly label: string
  readonly title?: string
  readonly persona?: 'owner' | 'fulfiller'
}

/** Provided by the shell around each routed view. `null` outside the shell (a test, a
 *  specimen), in which case `Page` reads its own `title` prop. */
export const PageRouteContext = createContext<PageRoute | null>(null)

export function usePageRoute(): PageRoute | null {
  return useContext(PageRouteContext)
}

export type PageProps = {
  /** The one h1. Defaults to the route's `title ?? label`. */
  readonly title?: ReactNode
  /** One line under the title: what this screen is for. */
  readonly lede?: ReactNode
  /** Where things stand, in one sentence, in the same place on every screen (UX-068). */
  readonly verdict?: ReactNode
  /** The screen's one primary action, and at most a reload beside it (UX-066). */
  readonly actions?: ReactNode
  /** Search, filters and sort. Folds as one unit on a narrow column. */
  readonly toolbar?: ReactNode
  /** Drawn in the list region instead of `children` when it is not null. */
  readonly empty?: ReactNode
  readonly children?: ReactNode
  /** An icon beside the title. */
  readonly icon?: IconName
  /** Draws `Loading` in the list region. The header keeps its shape (UX-098). */
  readonly loading?: boolean
  /** The answer to a press: a refusal, a retry, a notice. Pass `null` to reserve the slot
   *  before anything is in it; leave it out for a screen that never answers in place. The slot
   *  is at least one notice high either way, so a one-line answer never moves the rows (D118). */
  readonly status?: ReactNode
  /** The accessible name of the toolbar. */
  readonly toolbarLabel?: string
  readonly className?: string
}

export function Page({
  title,
  lede,
  verdict,
  actions,
  toolbar,
  empty,
  children,
  icon,
  loading,
  status,
  toolbarLabel = 'Filters',
  className,
}: PageProps) {
  const route = usePageRoute()
  const heading = title ?? route?.title ?? route?.label ?? null
  const titleId = useId()
  /* A PAGE WITH NO H1 IS A DEFECT THAT DRAWS NOTHING WRONG. With no `title` and no route around
     it, the page renders without its heading and nothing looks broken, so it says so in dev. */
  useEffect(() => {
    if (import.meta.env.DEV && heading === null) {
      console.error('<Page> has no title: pass `title`, or draw it inside the shell\'s PageRouteContext. A page with no h1 has no name for a screen reader.')
    }
  }, [heading])
  return (
    <main className={['bn-page', className].filter(Boolean).join(' ')} data-bn-page="" aria-labelledby={heading === null ? undefined : titleId}>
      <header className="bn-head bn-page-head">
        <div className="bn-head-text">
          {heading === null ? null : (
            <h1 className="bn-title" id={titleId} tabIndex={-1} data-bn-page-title="">
              {icon ? <Icon name={icon} size={22} /> : null}
              {heading}
            </h1>
          )}
          {lede ? <p className="bn-lede">{lede}</p> : null}
        </div>
        {actions ? <div className="bn-head-actions">{actions}</div> : null}
      </header>
      {verdict ? <Verdict>{verdict}</Verdict> : null}
      {toolbar ? <Toolbar label={toolbarLabel}>{toolbar}</Toolbar> : null}
      {status === undefined ? null : <StatusSlot>{status}</StatusSlot>}
      <div className="bn-page-body" aria-busy={loading ? 'true' : undefined}>
        {loading ? <Loading /> : empty ? empty : children}
      </div>
    </main>
  )
}

/** Where things stand. One sentence, directly under the title. */
export function Verdict({ children, className }: { readonly children: ReactNode; readonly className?: string }) {
  return (
    <p className={['bn-verdict', className].filter(Boolean).join(' ')} role="status">
      {children}
    </p>
  )
}

/** Search, filters and sort, as one unit. A wide column draws one row; a narrow one draws a
 *  grid of equal cells, so no control is wider than its neighbour for its label's sake. */
export function Toolbar({ children, label = 'Filters', className }: { readonly children: ReactNode; readonly label?: string; readonly className?: string }) {
  return (
    <div className={['bn-toolbar', className].filter(Boolean).join(' ')} role="group" aria-label={label}>
      {children}
    </div>
  )
}

/** THE STATUS SLOT HOLDS ITS SPACE (D118). It is at least one notice high whether or not a
 *  notice is in it, so a one-line answer to a press lands where the press was and moves nothing
 *  below it. A longer answer grows the slot rather than being cut: the sentence is never clipped.
 *  "What the server said" opens OVER the page, inside its gutter. */
export function StatusSlot({ children, className }: { readonly children?: ReactNode; readonly className?: string }) {
  return (
    <div className={['bn-status-slot', className].filter(Boolean).join(' ')} aria-live="polite">
      {children}
    </div>
  )
}

/** The one loading style, in the shape of what will replace it (UX-098): `rows` for a list,
 *  `cards` for a grid of tiles, `summary` for a band of figures that opens a screen. */
export function Loading({
  rows = 5,
  shape = 'rows',
  label = 'Loading',
  className,
}: {
  readonly rows?: number
  readonly shape?: 'rows' | 'cards' | 'summary'
  readonly label?: string
  readonly className?: string
}) {
  const count = Array.from({ length: rows }, (_, i) => i)
  return (
    <div className={['bn-loading', `bn-loading-${shape}`, className].filter(Boolean).join(' ')} role="status" aria-busy="true" data-shape={shape}>
      <span className="bn-sr">{label}</span>
      {shape === 'summary' ? (
        <>
          <span className="bn-skeleton bn-loading-headline" aria-hidden="true" />
          <span className="bn-loading-figures" aria-hidden="true">
            {[0, 1, 2, 3].map((i) => (
              <span key={i} className="bn-skeleton bn-loading-figure" />
            ))}
          </span>
        </>
      ) : shape === 'cards' ? (
        count.map((i) => (
          <div key={i} className="bn-loading-card" aria-hidden="true">
            <span className="bn-skeleton bn-loading-card-art" />
            <span className="bn-skeleton bn-loading-line" />
            <span className="bn-skeleton bn-loading-line bn-loading-line-short" />
          </div>
        ))
      ) : (
        count.map((i) => (
          <div key={i} className="bn-loading-row" aria-hidden="true">
            <span className="bn-skeleton bn-loading-thumb" />
            <span className="bn-loading-lines">
              <span className="bn-skeleton bn-loading-line" />
              <span className="bn-skeleton bn-loading-line bn-loading-line-short" />
            </span>
          </div>
        ))
      )}
    </div>
  )
}

/** A titled part of a page. The title is a heading a screen reader can jump to (UX-095): an h2
 *  on a page, an h3 inside a `Sheet` or `Modal` (whose own title is the h2), or the `level` you
 *  name. `lede` is one line under the title. Every other attribute (`id`, `data-*`, `aria-*`)
 *  reaches the `<section>`. */
export function Section({
  title,
  count,
  actions,
  lede,
  level,
  children,
  className,
  ...rest
}: Omit<HTMLAttributes<HTMLElement>, 'title'> & {
  readonly title: ReactNode
  readonly count?: ReactNode
  readonly actions?: ReactNode
  readonly lede?: ReactNode
  readonly level?: 2 | 3 | 4
  readonly children?: ReactNode
  readonly className?: string
}) {
  const id = useId()
  const inOverlay = useInOverlay()
  const depth = level ?? (inOverlay ? 3 : 2)
  const Heading = depth === 2 ? 'h2' : depth === 3 ? 'h3' : 'h4'
  return (
    <section className={['bn-section', className].filter(Boolean).join(' ')} aria-labelledby={id} {...rest}>
      <header className="bn-section-head">
        <Heading className={depth === 2 ? 'bn-h2' : 'bn-h3'} id={id}>
          {title}
          {count === undefined || count === null ? null : <span className="bn-section-count">{count}</span>}
        </Heading>
        {actions ? <div className="bn-section-actions">{actions}</div> : null}
      </header>
      {lede ? <p className="bn-section-lede">{lede}</p> : null}
      {children}
    </section>
  )
}
