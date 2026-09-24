import { createContext, useContext, useId } from 'react'
import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'

/* THE PAGE SCAFFOLD. Every screen is built from this from now on (D-one-page-width).
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

/** What the shell knows about the route a view is drawn for. */
export type PageRoute = {
  readonly path: string
  readonly label: string
  readonly title?: string
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
   *  before anything is in it; leave it out for a screen that never answers in place. The
   *  slot holds its height either way, so a notice never moves the rows (D118). */
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

/** THE STATUS SLOT HOLDS ITS SPACE (D118). It is one notice high whether or not a notice is
 *  in it, so the answer to a press lands where the press was and moves nothing below it. A
 *  notice drawn here should be `compact`: its one line fits the slot, and "What the server
 *  said" opens OVER the page rather than pushing it. */
export function StatusSlot({ children, className }: { readonly children?: ReactNode; readonly className?: string }) {
  return (
    <div className={['bn-status-slot', className].filter(Boolean).join(' ')} aria-live="polite">
      {children}
    </div>
  )
}

/** The one loading shape: rows the height of the rows that will replace them. */
export function Loading({ rows = 5, label = 'Loading', className }: { readonly rows?: number; readonly label?: string; readonly className?: string }) {
  return (
    <div className={['bn-loading', className].filter(Boolean).join(' ')} role="status" aria-busy="true">
      <span className="bn-sr">{label}</span>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="bn-loading-row" aria-hidden="true">
          <span className="bn-skeleton bn-loading-thumb" />
          <span className="bn-loading-lines">
            <span className="bn-skeleton bn-loading-line" />
            <span className="bn-skeleton bn-loading-line bn-loading-line-short" />
          </span>
        </div>
      ))}
    </div>
  )
}

/** A titled part of a page. The title is an h2, so every visible section title is a heading
 *  a screen reader can jump to (UX-095). */
export function Section({
  title,
  count,
  actions,
  children,
  className,
}: {
  readonly title: ReactNode
  readonly count?: ReactNode
  readonly actions?: ReactNode
  readonly children?: ReactNode
  readonly className?: string
}) {
  const id = useId()
  return (
    <section className={['bn-section', className].filter(Boolean).join(' ')} aria-labelledby={id}>
      <header className="bn-section-head">
        <h2 className="bn-h2" id={id}>
          {title}
          {count === undefined || count === null ? null : <span className="bn-section-count">{count}</span>}
        </h2>
        {actions ? <div className="bn-section-actions">{actions}</div> : null}
      </header>
      {children}
    </section>
  )
}
