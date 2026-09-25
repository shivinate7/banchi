import type { SVGProps } from 'react'

/* Banchi's icon set. 24-unit grid, 1.75 stroke, round joins — drawn in the Lucide idiom so
   the whole product speaks one line weight. Add an icon by adding a path; never inline an
   <svg> in a screen. */

const PATHS = {
  camera: 'M4 8h3l2-3h6l2 3h3v11H4z M12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  play: 'M6 4l14 8-14 8z',
  layers: 'M12 3l9 5-9 5-9-5z M3 13l9 5 9-5 M3 17l9 5 9-5',
  inbox: 'M3 13l3-8h12l3 8v6H3z M3 13h5l2 3h4l2-3h5',
  tag: 'M3 12V4h8l9 9-8 8z M7.5 8.5h.01',
  cart: 'M3 4h2l2.4 11h11l2-8H6.2 M9 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2z M18 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2z',
  truck: 'M3 6h11v10H3z M14 10h4l3 3v3h-7z M7 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4z M17 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4z',
  box: 'M21 8l-9-4-9 4v9l9 4 9-4z M3 8l9 4 9-4 M12 12v9',
  qr: 'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h2v2h-2z M18 14h2v2h-2z M14 18h2v2h-2z M18 18h2v2h-2z',
  hand: 'M8 11V5a1.5 1.5 0 0 1 3 0v6 M11 10V4a1.5 1.5 0 0 1 3 0v7 M14 11V6a1.5 1.5 0 0 1 3 0v8a6 6 0 0 1-6 6h-1a6 6 0 0 1-5-2.7L3 13.5a1.6 1.6 0 0 1 2.5-2L8 14',
  grid: 'M4 4h7v7H4z M13 4h7v7h-7z M4 13h7v7H4z M13 13h7v7h-7z',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z M20 20l-4-4',
  check: 'M5 12l5 5 9-10',
  x: 'M6 6l12 12 M18 6L6 18',
  plus: 'M12 5v14 M5 12h14',
  minus: 'M5 12h14',
  chevronDown: 'M6 9l6 6 6-6',
  chevronUp: 'M6 15l6-6 6 6',
  chevronLeft: 'M15 6l-6 6 6 6',
  chevronRight: 'M9 6l6 6-6 6',
  arrowRight: 'M5 12h14 M13 6l6 6-6 6',
  arrowLeft: 'M19 12H5 M11 6l-6 6 6 6',
  arrowUpRight: 'M7 17L17 7 M8 7h9v9',
  undo: 'M9 14L4 9l5-5 M4 9h10a6 6 0 0 1 0 12h-3',
  trash: 'M4 7h16 M10 11v6 M14 11v6 M6 7l1 13h10l1-13 M9 7V4h6v3',
  alert: 'M12 3l10 18H2z M12 10v5 M12 18h.01',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 11v5 M12 8h.01',
  sparkles: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z M19 17l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z',
  zap: 'M13 2L4 14h7l-1 8 9-12h-7z',
  clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 7v5l3 2',
  eye: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  image: 'M4 5h16v14H4z M4 16l5-5 4 4 3-3 4 4 M15.5 9.5h.01',
  refresh: 'M20 12a8 8 0 1 1-2.3-5.7 M20 4v5h-5',
  upload: 'M12 16V4 M7 9l5-5 5 5 M4 20h16',
  download: 'M12 4v12 M7 11l5 5 5-5 M4 20h16',
  keyboard: 'M3 6h18v12H3z M7 10h.01 M11 10h.01 M15 10h.01 M7 14h10',
  settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
  more: 'M5 12h.01 M12 12h.01 M19 12h.01',
  menu: 'M4 7h16 M4 12h16 M4 17h16',
  sun: 'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M12 2v2 M12 20v2 M4.9 4.9l1.4 1.4 M17.7 17.7l1.4 1.4 M2 12h2 M20 12h2 M4.9 19.1l1.4-1.4 M17.7 6.3l1.4-1.4',
  moon: 'M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z',
  dollar: 'M12 2v20 M17 6.5H9.5a3 3 0 0 0 0 6h5a3 3 0 0 1 0 6H6',
  trendUp: 'M3 17l6-6 4 4 8-8 M15 7h6v6',
  trendDown: 'M3 7l6 6 4-4 8 8 M15 17h6v-6',
  history: 'M3 12a9 9 0 1 0 3-6.7 M3 4v5h5 M12 7v5l3 2',
  scan: 'M3 8V5a2 2 0 0 1 2-2h3 M16 3h3a2 2 0 0 1 2 2v3 M21 16v3a2 2 0 0 1-2 2h-3 M8 21H5a2 2 0 0 1-2-2v-3 M7 12h10',
  pin: 'M12 22s7-6.5 7-12a7 7 0 1 0-14 0c0 5.5 7 12 7 12z M12 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  divider: 'M4 12h16 M8 4v4 M8 16v4 M16 4v4 M16 16v4',
  lock: 'M6 11h12v10H6z M9 11V7a3 3 0 0 1 6 0v4',
  unlock: 'M6 11h12v10H6z M9 11V7a3 3 0 0 1 5.5-1.7',
  flag: 'M5 21V4 M5 4h12l-2 4 2 4H5',
  filter: 'M3 5h18l-7 8v6l-4 2v-8z',
  columns: 'M4 4h16v16H4z M12 4v16',
  external: 'M14 4h6v6 M20 4l-9 9 M19 14v5H5V5h5',
  copy: 'M9 9h11v11H9z M5 15H4V4h11v1',
  circle: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z',
  dot: 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  command: 'M9 9V6a3 3 0 1 0-3 3h3z M15 9V6a3 3 0 1 1 3 3h-3z M9 15v3a3 3 0 1 1-3-3h3z M15 15v3a3 3 0 1 0 3-3h-3z M9 9h6v6H9z',
  rotate: 'M4 4v5h5 M4.6 9A8 8 0 1 1 4 13',
  film: 'M4 4h16v16H4z M4 9h16 M4 15h16 M9 4v16 M15 4v16',
  package: 'M21 8l-9-4-9 4v9l9 4 9-4z M3 8l9 4 9-4 M12 12v9 M7.5 6l9 4',
  wallet: 'M3 7h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z M3 7a2 2 0 0 1 2-2h11v2 M16 13h5v3h-5z',
  send: 'M22 2L11 13 M22 2l-7 20-4-9-9-4z',
  home: 'M3 11l9-8 9 8v10H3z M9 21v-6h6v6',
  mail: 'M3 6h18v12H3z M3 7l9 6 9-6',
  list: 'M8 6h13 M8 12h13 M8 18h13 M3 6h.01 M3 12h.01 M3 18h.01',
  hash: 'M4 9h16 M4 15h16 M10 3L8 21 M16 3l-2 18',
  paste: 'M9 3h6v3H9z M7 5H5v16h14V5h-2',
  ruler: 'M3 17L17 3l4 4L7 21z M8 12l2 2 M11 9l2 2 M14 6l2 2',
  wand: 'M15 4l5 5L9 20l-5-5z M15 4l-1.5 1.5 M18 7l-1.5 1.5 M4 4h.01 M9 2h.01 M20 12h.01 M20 19h.01 M2 12h.01',
  /* A lidded box with a handle strap — retiring a card is putting it away, not deleting it
     (`trash`) or shipping it (`package`/`box`). Added for the Retire control (owner's ruling,
     2026-09-20, "clearer icon only"): the bare `minus` read as unclear icon-only. */
  archive: 'M3 4h18v4H3z M4 8h16v11H4z M10 12h4',
  /* ONE ICON, ONE MEANING (UX-118). `history` meant four things: the graveyard, a product's
     history, the run list and a row's price history. These two take two of them over; the
     table under PATHS says which name means what. */
  headstone: 'M6 21V10a6 6 0 0 1 12 0v11 M4 21h16 M10 12h4 M12 10v5',
  chart: 'M4 4v16h16 M7 15l4-5 3 3 5-6',
  /* The eight icons the ICONOGRAPHY map added (`docs/specs/iconography.md` section 3), for the
     vocabulary `IconButton` draws from. Each is one meaning, in `ICON_MEANINGS` below. */
  /* A round seal with $: Mark sold. Not `tag` (Pricing's own meaning) and not a bare `dollar`
     (Sales' own meaning) — a THIRD, deliberately different mark for a THIRD meaning. */
  sold: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 6v12 M15.5 8H10a1.75 1.75 0 0 0 0 3.5h4a1.75 1.75 0 0 1 0 3.5H8.5',
  /* A pencil: Edit or Rename. The body, the tip, the underline it is about to write. */
  pencil: 'M4 20h4l11-11a2 2 0 0 0-3-3L5 17v3z M13 6l3 3',
  /* An eraser, angled, over the line it is about to remove: an undoable clear, never `trash`
     (which means gone for good). */
  eraser: 'M17 3l4 4-10.5 10.5H6L3 14z M11 6l7 7 M4 20h9',
  /* The `eye` with a line through it: Hide, the other half of `eye`'s Reveal. */
  eyeOff: 'M3 3l18 18 M10.6 5.1A10.7 10.7 0 0 1 22 12s-1.5 2.6-4.2 4.6 M6.2 7.4C4 9 2 12 2 12s4 7 10 7c1.3 0 2.6-.3 3.7-.8 M9.5 9.5a3 3 0 0 0 4.2 4.2',
  /* Two arrows, opposite ends, opposite directions: the sort direction toggle. `sortAsc` points
     up on the left (low to high); `sortDesc` points down on the left (high to low). Neither
     names the SORT KEY, which stays in words (FLT-19, UX-214) — only which way it runs. */
  sortAsc: 'M7 20V4 M7 4l-4 4 M7 4l4 4 M14 7h7 M14 12h7 M14 17h5',
  sortDesc: 'M7 4v16 M7 20l-4-4 M7 20l4-4 M14 7h5 M14 12h7 M14 17h7',
  /* An arrow into a bracket, deliberately NOT box-shaped (`box`, `package` and `archive` are
     already boxes, and a fourth would blur at 14px): Move to a box. */
  moveTo: 'M13 4h7v16h-7 M3 12h14 M13 7l4 5-4 5',
  /* Six dots, two columns of three: a drag handle. */
  grip: 'M9 6h.01 M9 12h.01 M9 18h.01 M15 6h.01 M15 12h.01 M15 18h.01',
} as const

/** WHAT AN ICON MEANS, where a meaning was ever in doubt (UX-118). A screen that draws one of
 *  these draws it for this meaning and no other; a new meaning is a new path. */
export const ICON_MEANINGS: Partial<Record<keyof typeof PATHS, string>> = {
  history: 'A log of past events, newest first: the run list',
  headstone: 'Cards that have left the store: the graveyard',
  chart: 'A price over time: a product or a row',
  archive: 'Retire a card: put it away, not delete it',
  refresh: 'Read again from the server: reload',
  undo: 'Take back the last press',
  trash: 'Delete for good',
  /* The ICONOGRAPHY vocabulary (`docs/specs/iconography.md` section 2, step 6): every icon
     `IconButton` draws from, so a call site is never a guess at what a glyph means. */
  sold: 'Mark a card sold',
  pencil: 'Edit or rename a stored fact',
  eraser: 'Clear a typed value; it can be undone',
  eyeOff: 'Hide what Reveal showed',
  sortAsc: 'Sort low to high',
  sortDesc: 'Sort high to low',
  moveTo: 'Move to a box',
  grip: 'Drag to reorder',
  copy: 'Copy to the clipboard',
  download: 'Save a file to disk',
  external: 'Open elsewhere',
  x: 'Close, dismiss, or clear one value',
  filter: 'Filter the list',
  settings: 'Manage, or the options for this row',
  more: 'More actions for this row',
  lock: 'Hold a price; it does not move',
  unlock: 'Release a held price',
  eye: 'Reveal what is hidden',
  chevronLeft: 'The previous item',
  chevronRight: 'The next item, or open this row',
  chevronUp: 'Collapse',
  chevronDown: 'Expand',
  search: 'Search',
  check: 'Confirm, or a completed state',
  hand: 'Fulfillment: a card the Fulfiller may pull',
}

export type IconName = keyof typeof PATHS

export type IconProps = SVGProps<SVGSVGElement> & {
  readonly name: IconName
  readonly size?: number
  readonly strokeWidth?: number
}

export function Icon({ name, size = 16, strokeWidth = 1.75, className, ...rest }: IconProps) {
  return (
    <svg
      className={['bn-icon', className].filter(Boolean).join(' ')}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      <path d={PATHS[name]} />
    </svg>
  )
}

export const ICON_NAMES = Object.keys(PATHS) as readonly IconName[]
