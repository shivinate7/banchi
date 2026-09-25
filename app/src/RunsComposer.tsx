import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent } from 'react'
import { createPortal } from 'react-dom'

import {
  cropPreview,
  describeFailure,
  getGames,
  getRuns,
  photoUrl,
  preflightRun,
  startRun,
  type Failure,
} from './server'
import type {
  BoxRecord,
  CropPreview,
  GameEntry,
  RunPreflight,
  RunSelection,
  RunStartFailure,
  RunStartedRun,
  RunSummary,
} from './types'
import { Button, Chip, EmptyState, Icon, Kbd, Notice, Segmented } from './kit'
import { toast } from './kit/toast'
import { LogWell } from './RunsLog'
import { useOverlayFocus } from './runsOverlay'
import { boxesLabel, boxLabel, runBoxLabel } from './runScope'
import { money } from './money'
import { storeKeyText } from './storeKey'
import { rememberSpendNotice, storedSpendNotice } from './deviceMemory'
import { carriedByBox, type CarriedScope } from './runHandoff'
import './Runs.css'

/* THE IDENTIFY COMPOSER — the one press on this product that spends money, as a staged
 * dialog: which cards, how they are read, what it costs, and a receipt.
 *
 * THE MONEY GATE IS TWO PRESSES AND NO TYPING (D33). `Check cost` runs the free preflight;
 * the confirm cannot be reached without it, and it carries the figure in its own label. The
 * estimate is void the moment the send moves — a term added, a drawer picked, a reading
 * changed — because a confirm whose first step described a different send is not a confirm.
 *
 * ONE PRESS, ONE SELECTION, ONE RUN, AND THE CART IS GONE. Stage 1 was "Which boxes" and built
 * a `RunLeg` per drawer, because `POST /pipeline/identify` refused any request without a
 * positive integer `box` — *"A run is always scoped to one box"* — so "identify everything that
 * still needs it" was not a sentence this screen could say, and a pile spanning two drawers was
 * two presses however few cards it held. `pipeline/selection.py` replaced that with one
 * `Selection` whose every term NARROWS, so stage 1 is a SELECTION BUILDER: one start, then
 * chips that narrow it.
 *
 * WHAT THE CART COST, MEASURED, is why none of its shape is kept for symmetry. Three separate
 * presses over three drawers created three run directories in the same second on 2026-09-01 —
 * one press by the operator's reckoning and three runs by the product's — and 13 of 13 scope
 * blocks on this store record `whole_box: true`, so the per-leg reading the cart existed to
 * carry was never once used. The reading is per PRESS now (`RunSend`), and an operator who
 * wants box 3 at 1200 and box 5 at 900 presses twice.
 *
 * THE MULTI-SELECT DRAWER GRID SURVIVES INTACT AND IS LOAD-BEARING. `box` is list-valued on the
 * wire precisely so that the 2026-09-01 press is still ONE press — three drawers ticked, one
 * cost check, one run instead of three. What changed under it is the response, not the gesture.
 *
 * `Runs.tsx` OWNS THE SELECTION; this dialog owns the reading, the money gate and everything
 * after the press. The drawer names travel beside the selection for the screen (D56) and are
 * never sent. */

/* D32's measured frontier over box 2, against a full-frame @1568 baseline of $0.72. */
const READINGS = [
  {
    key: 'measured',
    label: 'Measured best',
    crop: true,
    maxEdge: 1200,
    says: 'Crops to the card, 1200px.',
  },
  {
    key: 'cheapest',
    label: 'Cheapest',
    crop: true,
    maxEdge: 900,
    says: 'Crops to the card, 900px. Costs less, and the card number is a little softer.',
  },
  {
    key: 'whole',
    label: 'Whole frame',
    crop: false,
    maxEdge: 1568,
    says: 'The whole photograph, 1568px. Costs the most.',
  },
] as const

const CUSTOM_SAYS =
  'Your own crop and size. Between 900 and 1400px works best.'

type ReadingKey = (typeof READINGS)[number]['key'] | 'custom'

/** How a press is read until somebody says otherwise: D32's measured-best pair. ONE reading for
 *  the press, where it used to be one per drawer — see the header. */
const DEFAULT_READING = { crop: true, maxEdge: 1200, custom: false }
type Reading = typeof DEFAULT_READING

/* ------------------------------------------------------------------ the selection builder */

/**
 * WHERE THE SELECTION STARTS. Four of them, and each names exactly one term of
 * `RunSelection` — so whichever is chosen, the press is BOUNDED by something the operator
 * pointed at. The narrowing chips below then apply on top of any of them.
 *
 * THE STATE OF THE STORE IS THE DEFAULT BECAUSE IT IS WHAT "IDENTIFY MY CARDS" MEANS. Every
 * other start answers a narrower question the operator had to have in mind first.
 */
export type StartKey = 'needed' | 'drawers' | 'ticked' | 'run'

/**
 * WHAT THE OPERATOR HAS POINTED AT, in the screen's own vocabulary rather than the wire's.
 *
 * IT IS NOT A `RunSelection` AND THAT IS THE POINT. A draft holds things the wire has no term
 * for — which start is chosen, a drawer pick kept while another start is showing, a `since`
 * bound in THIS DEVICE's wall clock — and `selectionOf` below is the one function that turns it
 * into the wire's shape. Two shapes because they answer different questions: this one is what
 * the controls hold, and that one is what the press is over.
 *
 * A PICK IS KEPT WHEN ITS START IS NOT SHOWING, which the cart already did for the reading: the
 * drawers stay ticked while "Everything that needs it" is chosen, so switching back does not
 * silently reset a pick made on purpose. `selectionOf` reads only the terms the chosen start
 * actually names, so nothing kept here can leak onto the wire.
 */
export type SelectionDraft = {
  readonly start: StartKey
  /** Ascending, and only ever sent under the `drawers` start. */
  readonly boxes: readonly number[]
  readonly run: string | null
  readonly game: string | null
  readonly section: number | null
  /** The `datetime-local` control's own value — this device's wall clock, NOT the wire's
   *  instant. `sinceOnTheWire` converts, and the comment there is the whole reason for the
   *  distinction. */
  readonly since: string | null
}

/** Nothing pointed at yet: the store-wide start, no drawer picked, nothing narrowed. */
export const NO_DRAFT: SelectionDraft = {
  start: 'needed',
  boxes: [],
  run: null,
  game: null,
  section: null,
  since: null,
}

/**
 * THE `datetime-local` VALUE THIS CONTROL HOLDS, AS THE INSTANT THE WIRE COMPARES.
 *
 * `pipeline/selection.py` compares `since` against each card's `captured_at` as a STRING, on the
 * argument that `store/master.py:now()` writes every stamp through one function so lexicographic
 * order IS chronological order over them. Those stamps are UTC — `2026-09-12T14:30:00.000+00:00`
 * — and a `datetime-local` input holds the operator's wall clock with no offset at all. Sending
 * the control's value raw would compare a local clock against UTC stamps and be wrong by this
 * Mac's offset, which on the rig is seven or eight hours: a "today" bound would quietly include
 * or exclude an evening's whole sitting.
 *
 * SO THE CONTROL SPEAKS THE OPERATOR'S CLOCK AND THE WIRE SPEAKS THE STORE'S, and this is the
 * one line between them. `new Date('2026-09-12T00:00')` parses as local time by specification,
 * and `toISOString` is the same instant in UTC.
 *
 * THE SUFFIX IS DROPPED ON PURPOSE, and it is the one detail here that is not obvious.
 * `toISOString` ends in `Z`; the store's stamps end in `+00:00`; and `Z` (0x5A) sorts ABOVE `+`
 * (0x2B), so a card photographed at exactly the bound would compare as BEFORE it and be dropped
 * from a press the operator asked to include. Truncating to `2026-09-12T07:00:00` leaves the
 * stamp the longer string at every equal prefix, so the boundary card is included — which is
 * what "since" means. `_since_of`'s own regex is a `re.match` over `YYYY-MM-DD[THH:MM[:SS]]`,
 * so the truncated form is exactly what it accepts.
 */
export function sinceOnTheWire(local: string): string | null {
  const when = new Date(local)
  if (Number.isNaN(when.getTime())) return null
  return when.toISOString().slice(0, 19)
}

/** Local midnight, in the shape a `datetime-local` input holds. The one-press "today" — a
 *  sitting is reduced to a `since` bound, because the server has no `sitting` term and a second
 *  clustering in Python would be a second answer to Home's question. */
export function todayLocal(at: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}T00:00`
}

/**
 * THE DRAFT AS THE WIRE'S SELECTION. One function, so the footer's own sentence, the preflight
 * and the confirm cannot describe three different sends.
 *
 * EVERY TERM IS OMITTED WHERE IT IS UNSET, never sent as null or empty — `server.ts:onTheWire`
 * makes the same promise one layer down, because the route reads absence as "this term does not
 * narrow" and refuses an empty array outright.
 *
 * `bid` AND `paths` ARE DELIBERATELY ABSENT AND ARE NOT COMING. D145 rules that a drawer's true
 * index must never be rendered anywhere in this app — *"a box needs an index # not visible
 * anywhere in the app"* — so `bid` is a CLI and wire term only, and a screen that offered it
 * would be drawing the join key beside the number a person counts to. `paths` is a file dialog a
 * browser cannot honestly draw over the server's disk; naming a capture directory is a terminal
 * affordance. Both terms stay reachable from `pkmnscan identify`, which is where they belong.
 *
 * A SECTION NEEDS EXACTLY ONE DRAWER AND IS STRUCTURALLY OMITTED OTHERWISE.
 * `pipeline/selection.py:check` refuses the combination BY NAME — *"Section 2 is a different set
 * of cards in every box"* — and the control disables itself for the same reason. Both: the
 * control is the honesty, and this is the guard, so a stale value can never reach a refusal the
 * operator did not cause.
 */
export function selectionOf(draft: SelectionDraft, carried: CarriedScope | null): RunSelection {
  const out: RunSelection = {}
  if (draft.start === 'needed') {
    /* `captured` is `store/master.py:CAPTURED` — a card that has been photographed and not yet
       identified, which is the whole of what "needs it" means. */
    out.state = 'captured'
  } else if (draft.start === 'drawers') {
    if (draft.boxes.length > 0) out.box = [...draft.boxes]
  } else if (draft.start === 'ticked') {
    /* THE HANDOFF IS ALREADY POSITION KEYS. `runHandoff.ts:CarriedScope` moved from `{box,
       indices}` to a flat list of `box/index` strings so a tick list from `#/inventory` can
       span drawers — `keys` is the spelling the cache, the queues, the join and D174's claim
       table already use, so this is a pass-through rather than a composition. */
    if (carried !== null && carried.keys.length > 0) out.keys = [...carried.keys]
  } else if (draft.run !== null) {
    out.run = draft.run
  }
  if (draft.game !== null) out.game = draft.game
  if (draft.section !== null && out.box?.length === 1) out.section = draft.section
  if (draft.since !== null) {
    const instant = sinceOnTheWire(draft.since)
    if (instant !== null) out.since = instant
  }
  return out
}

/**
 * IS THE START ANSWERED? The gate on both presses, and it is not cosmetic.
 *
 * A SELECTION THAT NAMES NOTHING IS EVERY PHOTOGRAPH IN THE STORE, and this route ACCEPTS that
 * — `Selection.named` is false, the route does not refuse it, and `flags()` emits `--all` so the
 * child does not refuse itself either. The asymmetry is argued there: the screen has the free
 * preflight and a confirm in front of it, a terminal has a newline. Which means an operator who
 * chose "Drawers" and ticked none must NOT be able to press: their press would be 2,535
 * photographs under a heading that says one drawer. So each start is gated on its own term
 * rather than on the selection being non-empty.
 */
export function startAnswered(draft: SelectionDraft, carried: CarriedScope | null): boolean {
  if (draft.start === 'needed') return true
  if (draft.start === 'drawers') return draft.boxes.length > 0
  if (draft.start === 'ticked') return carried !== null && carried.keys.length > 0
  return draft.run !== null
}

/**
 * WHAT THIS PRESS IS OVER, IN THE SCREEN'S OWN WORDS — for the footer note and the page's pill,
 * BEFORE anything has been quoted.
 *
 * `RunPreflight.sentence` IS THE SERVER'S AND IS RENDERED VERBATIM WHERE IT EXISTS. This is a
 * second sentence about the same thing and that is a deliberate, narrow duplication: there is no
 * free route that describes a selection — `POST /pipeline/preflight` shells out to
 * `identify --dry-run` — and the footer has to say what the operator is about to check the cost
 * of. So this one names the terms and the quote's own line names them in the pipeline's words,
 * and the quote's is the one that is authoritative about what was scanned.
 */
export function selectionLine(
  draft: SelectionDraft,
  carried: CarriedScope | null,
  boxes: readonly BoxRecord[] | null,
): string {
  const named = (box: number) => boxLabel(box, boxes?.find((row) => row.box === box)?.name)
  const parts: string[] = []
  if (draft.start === 'needed') {
    parts.push('Every card waiting to be identified')
  } else if (draft.start === 'drawers') {
    if (draft.boxes.length === 0) return 'Pick a box. You can pick several.'
    parts.push(
      draft.boxes.length === 1
        ? (named(draft.boxes[0] ?? 0) ?? '')
        : `${draft.boxes.length} boxes: ${draft.boxes.map((box) => named(box) ?? '').join(', ')}`,
    )
  } else if (draft.start === 'ticked') {
    if (carried === null || carried.keys.length === 0) return 'No cards were handed over.'
    const legs = carriedByBox(carried)
    parts.push(`${plural(carried.keys.length, 'ticked card')} in ${boxesLabel(legs) ?? ''}`)
  } else {
    if (draft.run === null) return 'Pick a run to read again.'
    parts.push(`the cards of ${draft.run}`)
  }
  if (draft.section !== null && draft.boxes.length === 1 && draft.start === 'drawers') {
    parts.push(`section ${draft.section}`)
  }
  if (draft.game !== null) parts.push(draft.game)
  if (draft.since !== null) parts.push(`photographed since ${draft.since.replace('T', ' ')}`)
  return parts.join(', ')
}

type StageKey = 'select' | 'read' | 'quote' | 'started'
const ORDER: readonly StageKey[] = ['select', 'read', 'quote', 'started']
const STAGE_LIST: readonly { readonly key: StageKey; readonly n: string; readonly label: string }[] = [
  { key: 'select', n: '1', label: 'Cards' },
  { key: 'read', n: '2', label: 'Photos' },
  { key: 'quote', n: '3', label: 'Cost' },
]
const TITLES: Record<StageKey, string> = {
  select: 'Which cards',
  read: 'How the photos are sent',
  quote: 'What it costs',
  started: 'Started',
}

function count(value: number | null | undefined): string {
  return typeof value === 'number' ? String(value) : '—'
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

/** The next whole dollar at or above a figure, floored at the notice's own default. What the
 *  one-press raise sets, so "stop asking" means this send AND the ones like it rather than this
 *  send to the cent. */
function coverFor(estimate: number): number {
  return Math.max(1, Math.ceil(estimate))
}

type Props = {
  readonly open: boolean
  readonly onClose: () => void
  /** The wire's shape, derived by `Runs.tsx` through `selectionOf` — passed rather than
   *  recomputed so the page's pill and this dialog cannot disagree about the press. */
  readonly selection: RunSelection
  readonly draft: SelectionDraft
  readonly onDraft: (patch: Partial<SelectionDraft>) => void
  readonly boxes: readonly BoxRecord[] | null
  readonly boxesFailure: Failure | null
  readonly onToggleBox: (box: number) => void
  readonly carried: CarriedScope | null
  readonly onDropCarried: () => void
  readonly onStarted: (run: string) => void
}

export function RunsComposer({
  open,
  onClose,
  selection,
  draft,
  onDraft,
  boxes,
  boxesFailure,
  onToggleBox,
  carried,
  onDropCarried,
  onStarted,
}: Props) {
  const dialog = useRef<HTMLDivElement | null>(null)
  const [stage, setStage] = useState<StageKey>('select')

  /* ONE READING FOR THE PRESS. `RunSend` carries one `crop` and one `maxEdge`, so this is a
     single value where it used to be a map keyed by box. */
  const [reading, setReading] = useState<Reading>(DEFAULT_READING)
  const patchReading = useCallback((patch: Partial<Reading>) => {
    setReading((held) => ({ ...held, ...patch }))
  }, [])

  /* The preflight's answer — step one of the money gate — and the send it was quoted for. */
  const [quote, setQuote] = useState<RunPreflight | null>(null)
  const [ticket, setTicket] = useState('')
  const [showPreflight, setShowPreflight] = useState(false)

  /* THE SPEND NOTICE (the owner's ruling, 2026-09-12). Device-local, raisable here, and never a
     block — see `deviceMemory.ts` for the derivation of the default and for why a ceiling is the
     wrong shape. `raised` keeps the block on screen after the press that raised it, so pressing
     it cannot move the confirm underneath the finger (D118). */
  const [notice, setNotice] = useState<number>(() => storedSpendNotice())
  const [raised, setRaised] = useState<number | null>(null)

  const [busy, setBusy] = useState<'quote' | 'start' | null>(null)
  const [trouble, setTrouble] = useState<Failure | null>(null)
  const [partial, setPartial] = useState<RunStartFailure[] | null>(null)
  const [started, setStarted] = useState<{
    readonly runs: RunStartedRun[]
    readonly estimate: number | null
    readonly cards: number | null
  } | null>(null)

  /* The crop preview. */
  const [preview, setPreview] = useState<CropPreview | null>(null)
  const [previewFor, setPreviewFor] = useState('')
  const [previewOffset, setPreviewOffset] = useState(0)
  const [previewBusy, setPreviewBusy] = useState(false)
  const [previewTrouble, setPreviewTrouble] = useState<string | null>(null)
  const [aim, setAim] = useState<{ x: number; y: number } | null>(null)
  const detailRef = useRef<HTMLDivElement | null>(null)

  /* The two pickers stage 1 needs and the run list it cannot have from here. Both are read when
     the dialog opens rather than at mount, because this component renders `null` while closed
     and a fetch for a control nobody has opened is a fetch nobody asked for. */
  const [games, setGames] = useState<readonly GameEntry[] | null>(null)
  const [runs, setRuns] = useState<readonly RunSummary[] | null>(null)
  const [runsTrouble, setRunsTrouble] = useState<string | null>(null)

  /* WHAT WOULD ACTUALLY BE SENT, in the shape `server.ts` puts on the wire. One derivation feeds
     the preflight, the preview, the confirm and the void key below. */
  const send = useMemo(
    () => ({ selection, crop: reading.crop, maxEdge: reading.maxEdge }),
    [selection, reading],
  )

  /* The whole send as one string, so an effect can compare it. Spelled out term by term rather
     than stringified: `JSON.stringify` over an object is key-ORDER sensitive, so a selection
     built by a different branch of `selectionOf` would read as a different send and silently
     void a paid-for quote. */
  const sendKey = useMemo(
    () =>
      [
        selection.state ?? '',
        (selection.box ?? []).join(','),
        selection.section ?? '',
        selection.game ?? '',
        selection.since ?? '',
        (selection.keys ?? []).join(','),
        selection.run ?? '',
        reading.crop ? 'crop' : 'whole',
        reading.maxEdge,
      ].join('|'),
    [selection, reading],
  )

  const scoped = startAnswered(draft, carried)
  const line = useMemo(() => selectionLine(draft, carried, boxes), [draft, carried, boxes])

  /* THE QUOTE IS VOID THE MOMENT THE SEND MOVES. */
  useEffect(() => {
    if (ticket !== '' && ticket !== sendKey) {
      setQuote(null)
      setTicket('')
    }
  }, [sendKey, ticket])

  /* And the cost stage cannot stand without a quote under it. */
  useEffect(() => {
    if (stage === 'quote' && quote === null && busy !== 'quote') {
      setStage('read')
      toast({
        kind: 'status',
        title: 'Estimate retired',
        body: 'The selection changed. Check the cost again before spending.',
      })
    }
  }, [stage, quote, busy])

  /* Every way out goes through this one wrapper — the X, the scrim, "Watch the run" and
     Escape — so a spent receipt is reset however the dialog was left. */
  const close = useCallback(() => {
    onClose()
    if (stage === 'started') {
      setStage('select')
      setStarted(null)
      setPartial(null)
    }
  }, [onClose, stage])

  /* Dialog chrome: focus lands inside on open, stays inside under Tab, and goes back to the
     button that opened it on close. Escape closes. */
  useOverlayFocus(dialog, open, close)

  /* ------------------------------------------------------------------- the stage 1 pickers */
  useEffect(() => {
    if (!open || games !== null) return
    let live = true
    void (async () => {
      try {
        const answer = await getGames()
        if (live) setGames(answer.games)
      } catch {
        /* The game chip is a NARROWING control and nothing depends on it: a registry that will
           not answer leaves the chip out and every other term still presses. The page's own
           failure statement is drawn by the run panel, and a second one here for an optional
           filter would be noise over a screen that still works. */
        if (live) setGames([])
      }
    })()
    return () => {
      live = false
    }
  }, [open, games])

  /* The run picker's list, read only once the operator asks for that start — it is the one
     picker here whose route the run panel is already polling, and a press that never chooses
     "A previous run's cards" should not pay for it. */
  useEffect(() => {
    if (!open || draft.start !== 'run' || runs !== null) return
    let live = true
    void (async () => {
      try {
        const answer = await getRuns()
        if (!live) return
        setRuns(answer)
        setRunsTrouble(null)
      } catch (err) {
        if (!live) return
        setRuns([])
        setRunsTrouble(describeFailure(err).message)
      }
    })()
    return () => {
      live = false
    }
  }, [open, draft.start, runs])

  /* ------------------------------------------------------------------ the crop preview */
  const previewKey = showingKey(sendKey)
  const showing = open && stage === 'read'

  /* Debounced at 140ms: under a key repeat, over a human tap. The previous card stays up,
     dimmed, while the next is fetched. */
  useEffect(() => {
    if (!showing || !scoped) {
      setPreview(null)
      setPreviewFor('')
      return
    }
    const want = `${previewKey}:${previewOffset}`
    if (previewFor === want) return
    let live = true
    const timer = setTimeout(() => {
      setPreviewBusy(true)
      void (async () => {
        try {
          const answer = await cropPreview(send, previewOffset)
          if (!live) return
          setPreview(answer)
          setPreviewTrouble(null)
        } catch (err) {
          if (!live) return
          setPreview(null)
          setPreviewTrouble(describeFailure(err).message)
        } finally {
          if (live) {
            setPreviewFor(want)
            setPreviewBusy(false)
          }
        }
      })()
    }, 140)
    return () => {
      live = false
      clearTimeout(timer)
    }
  }, [showing, scoped, previewKey, previewOffset, previewFor, send])

  useEffect(() => {
    setAim(null)
  }, [previewFor])

  /* A changed SELECTION starts at the front of its own walk — a different set of photographs is
     a different walk, and card 400 of a drawer is not card 400 of the store. A changed READING
     deliberately does not reset it: D32's whole argument for the preview is holding one card
     still while the pair moves under it. */
  useEffect(() => {
    setPreviewOffset(0)
  }, [selection])

  const stepPreview = useCallback(
    (by: number) =>
      setPreviewOffset((was) => {
        const total = preview?.total ?? 0
        return total > 0 ? (was + by + total) % total : Math.max(0, was + by)
      }),
    [preview],
  )

  /* Arrow keys walk the selection while the preview is on screen — guarded on the target so a
     number input keeps its caret keys, and modifier chords are left to the shell. */
  useEffect(() => {
    if (!showing || !scoped) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const target = event.target as HTMLElement | null
      const tag = target?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target?.isContentEditable) return
      event.preventDefault()
      stepPreview(event.key === 'ArrowRight' ? 1 : -1)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [showing, scoped, stepPreview])

  /* The 1:1 window's position in the sent image's own pixels, clamped into the image. */
  const detailPosition = useMemo(() => {
    const sample = preview?.sample
    if (sample?.sent == null) return undefined
    const [sentW, sentH] = sample.sent
    const node = detailRef.current
    const viewW = node?.offsetWidth ?? 300
    const viewH = node?.offsetHeight ?? 140
    let x: number
    let y: number
    if (aim !== null) {
      x = aim.x
      y = aim.y
    } else if (sample.band_rect != null) {
      x = sample.band_rect[0]
      y = sample.band_rect[1] + (sample.band_rect[3] - sample.band_rect[1] - viewH) / 2
    } else {
      x = (sentW - viewW) / 2
      y = (sentH - viewH) / 2
    }
    x = Math.max(0, Math.min(x, Math.max(0, sentW - viewW)))
    y = Math.max(0, Math.min(y, Math.max(0, sentH - viewH)))
    return `${-Math.round(x)}px ${-Math.round(y)}px`
  }, [preview, aim])

  const aimAt = useCallback(
    (event: PointerEvent<HTMLDivElement>) => {
      const sample = preview?.sample
      if (sample?.frame == null || sample.sent == null) return
      const node = detailRef.current
      const box = event.currentTarget.getBoundingClientRect()
      if (box.width === 0 || box.height === 0) return
      const [frameW, frameH] = sample.frame
      const cut = sample.rect ?? [0, 0, frameW, frameH]
      const originalX = ((event.clientX - box.left) / box.width) * frameW
      const originalY = ((event.clientY - box.top) / box.height) * frameH
      const sentX = ((originalX - cut[0]) / (cut[2] - cut[0])) * sample.sent[0]
      const sentY = ((originalY - cut[1]) / (cut[3] - cut[1])) * sample.sent[1]
      setAim({ x: sentX - (node?.offsetWidth ?? 300) / 2, y: sentY - (node?.offsetHeight ?? 140) / 2 })
    },
    [preview],
  )

  /* ------------------------------------------------------------------- the two presses */
  const guard = useCallback(async (key: 'quote' | 'start', work: () => Promise<void>) => {
    setBusy(key)
    setTrouble(null)
    try {
      await work()
    } catch (err) {
      setTrouble(describeFailure(err))
    } finally {
      setBusy(null)
    }
  }, [])

  const doQuote = useCallback(
    () =>
      guard('quote', async () => {
        const answer = await preflightRun(send)
        setQuote(answer)
        setTicket(sendKey)
        setShowPreflight(false)
        setRaised(null)
        setStage('quote')
      }),
    [guard, send, sendKey],
  )

  /* OPEN, THEN SPEND (the owner's Q5 ruling, D33 kept). The cost check is free, so it runs the
     moment the sheet opens over cards it can already name: the press that carried the scope
     (Capture's box, Home's waiting cards) is the first press, and Spend is the second. The
     spend press still does not exist until the figure is on screen. Once per opening: going
     back to change the cards does not re-run it behind the operator's back. */
  const autoQuoted = useRef(false)
  useEffect(() => {
    if (!open) {
      autoQuoted.current = false
      return
    }
    if (autoQuoted.current || !scoped || stage !== 'select' || quote !== null || busy !== null) return
    autoQuoted.current = true
    void doQuote()
  }, [open, scoped, stage, quote, busy, doQuote])

  const doStart = () =>
    guard('start', async () => {
      const answer = await startRun(send)
      setStarted({
        runs: answer.started,
        estimate: quote?.total.estimate_usd ?? null,
        cards: quote?.total.to_send ?? null,
      })
      /* The quote is spent: identifying more needs a fresh preflight. */
      setQuote(null)
      setTicket('')
      setPartial(answer.failed.length > 0 ? answer.failed : null)
      setStage('started')
      const first = answer.started[0]
      if (first !== undefined) {
        onStarted(first.run)
        toast({
          kind: 'ok',
          title: `${runLabel(first, boxes) ?? line} started`,
          body: `${money(quote?.total.estimate_usd)} (${plural(quote?.total.to_send ?? 0, 'card')})`,
        })
      }
    })

  const raiseNotice = useCallback(
    (to: number) => {
      setNotice(to)
      setRaised(to)
      rememberSpendNotice(to)
    },
    [],
  )

  /* ---------------------------------------------------------------------------- render */
  const rows = useMemo(() => (boxes === null ? [] : [...boxes].sort((a, b) => a.box - b.box)), [boxes])

  /* The one drawer a section can be a divider inside, and its dividers. Null whenever the
     section control has nothing to offer — which the control draws as a reason rather than as an
     empty select. */
  const sectionsOf = useMemo(() => {
    if (draft.start !== 'drawers' || draft.boxes.length !== 1) return null
    return rows.find((row) => row.box === draft.boxes[0]) ?? null
  }, [draft.start, draft.boxes, rows])

  const stageState = (key: StageKey): 'done' | 'current' | 'todo' =>
    stage === 'started' ? 'done' : ORDER.indexOf(key) < ORDER.indexOf(stage) ? 'done' : key === stage ? 'current' : 'todo'

  if (!open) return null

  const readingMatch = READINGS.find((r) => r.crop === reading.crop && r.maxEdge === reading.maxEdge) ?? null
  const readingValue: ReadingKey = reading.custom ? 'custom' : (readingMatch?.key ?? 'custom')
  const readingOptions = [
    ...READINGS.map((option) => ({
      value: option.key as ReadingKey,
      label: (
        <>
          <span>{option.label}</span>
          <span className="run-reading-edge">{option.maxEdge}</span>
        </>
      ),
    })),
    { value: 'custom' as ReadingKey, label: 'Custom' },
  ]

  /* The ticked start is offered only while something HAS been ticked, which is D39's re-consent
     rule: the handoff is produced by `#/inventory`'s one mass-select and cannot be rebuilt here
     (`runHandoff.ts` has the argument), so once it is dropped the way back is that screen. */
  const startOptions = [
    { value: 'needed' as StartKey, label: 'Everything that needs it', icon: 'layers' as const },
    { value: 'drawers' as StartKey, label: 'Boxes', icon: 'box' as const },
    ...(carried === null
      ? []
      : [{ value: 'ticked' as StartKey, label: 'The cards I ticked', icon: 'check' as const }]),
    { value: 'run' as StartKey, label: 'A previous run’s cards', icon: 'history' as const },
  ]

  const estimate = quote?.total.estimate_usd ?? null
  const overNotice = estimate !== null && estimate > notice

  /* Portalled to <body>: `.bn-page`'s enter animation leaves `main` with a filled transform,
     which makes it the containing block for anything fixed inside it — a dialog drawn there
     centres on the page column rather than the viewport and the scrim never reaches the nav. */
  return createPortal(
    <>
      <div className="bn-scrim" onClick={close} />
      <div
        ref={dialog}
        className="bn-dialog runs-composer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="runs-composer-title"
        tabIndex={-1}
      >
        <header className="runs-composer-head">
          <div className="runs-composer-heading">
            <span className="bn-eyebrow">
              <span>Identify</span>
              <span>costs money</span>
            </span>
            <h2 className="runs-composer-title" id="runs-composer-title">
              {TITLES[stage]}
            </h2>
          </div>
          <ol className="runs-stages" aria-label="Stages">
            {STAGE_LIST.map((row) => {
              const state = stageState(row.key)
              const canGo = state === 'done' && stage !== 'started'
              return (
                <li key={row.key}>
                  {canGo ? (
                    <button type="button" className="runs-stage" data-state={state} onClick={() => setStage(row.key)}>
                      <span className="runs-stage-n">
                        <Icon name="check" size={11} />
                      </span>
                      <span className="runs-stage-label">{row.label}</span>
                    </button>
                  ) : (
                    <span className="runs-stage" data-state={state} aria-current={state === 'current' ? 'step' : undefined}>
                      <span className="runs-stage-n">{state === 'done' ? <Icon name="check" size={11} /> : row.n}</span>
                      <span className="runs-stage-label">{row.label}</span>
                    </span>
                  )}
                </li>
              )
            })}
          </ol>
          <Button variant="ghost" icon="x" iconOnly onClick={close}>
            Close
          </Button>
        </header>

        <div className="runs-composer-body">
          {trouble === null ? null : (
            <Notice tone="danger" code={trouble.code}>
              {trouble.message}
            </Notice>
          )}

          {/* ---------------------------------------------------------- 1 · which cards */}
          {stage === 'select' ? (
            <div className="runs-composer-stage" key="select">
              {boxesFailure === null ? null : (
                <Notice tone="danger" code={boxesFailure.code}>
                  {boxesFailure.message}
                </Notice>
              )}

              <Segmented<StartKey>
                className="runs-starts"
                label="Where the selection starts"
                value={draft.start}
                options={startOptions}
                onChange={(next) => onDraft({ start: next })}
              />

              {/* ONE PANEL, WHICHEVER START IS CHOSEN, so pressing a segment changes what is in
                  the slot and never where the rest of the sheet is (D118). */}
              <div className="runs-pick">
                {draft.start === 'needed' ? (
                  <div className="runs-pick-said">
                    <p className="runs-pick-lede">Every card photographed and not yet identified, in any box.</p>
                  </div>
                ) : null}

                {draft.start === 'drawers' ? (
                  <div className="runs-boxes" role="group" aria-label="Which boxes to identify">
                    {boxes === null && boxesFailure === null ? (
                      Array.from({ length: 6 }, (_, i) => <div key={i} className="bn-skeleton runs-box-skel" />)
                    ) : rows.length === 0 ? (
                      <EmptyState
                        icon="box"
                        title="No boxes yet"
                        body="Capture a card to start a run."
                        actions={
                          <Button
                            icon="camera"
                            onClick={() => {
                              window.location.hash = '#/capture'
                            }}
                          >
                            Go to capture
                          </Button>
                        }
                      />
                    ) : (
                      rows.map((record, i) => {
                        const on = draft.boxes.includes(record.box)
                        return (
                          <button
                            key={record.box}
                            type="button"
                            className="runs-box"
                            aria-pressed={on}
                            onClick={() => onToggleBox(record.box)}
                            style={{ animationDelay: `${Math.min(i, 12) * 30}ms` }}
                          >
                            <span className="runs-box-num" aria-hidden="true">
                              {record.box}
                            </span>
                            <span className="runs-box-text">
                              <span className="runs-box-name" title={boxLabel(record.box, record.name)}>
                                {boxLabel(record.box, record.name)}
                              </span>
                              <span className="runs-box-cards">{plural(record.cards, 'card')}</span>
                            </span>
                            <span className="runs-box-check" aria-hidden="true">
                              <Icon name="check" size={12} />
                            </span>
                          </button>
                        )
                      })
                    )}
                  </div>
                ) : null}

                {draft.start === 'ticked' ? (
                  carried === null ? (
                    <EmptyState
                      icon="check"
                      title="Nothing was handed over"
                      body="Select cards on Inventory to run them."
                      actions={
                        <Button
                          icon="grid"
                          onClick={() => {
                            window.location.hash = '#/inventory'
                          }}
                        >
                          Go to inventory
                        </Button>
                      }
                    />
                  ) : (
                    (() => {
                      /* THE HANDOFF CAN SPAN DRAWERS NOW (runHandoff.ts's `CarriedScope` is a
                         flat list of `box/index` keys), so the lede and the way-out button read
                         off `carriedByBox` rather than a single `box`/`indices` pair. A tick
                         list from one drawer — the only case `#/inventory`'s walk produces
                         today — keeps the exact wording this button has always had. */
                      const legs = carriedByBox(carried)
                      const only = legs.length === 1 ? legs[0] : undefined
                      return (
                        <div className="runs-pick-said">
                          <p className="runs-pick-lede">
                            {plural(carried.keys.length, 'card')} ticked in {boxesLabel(legs) ?? ''}. Only those
                            cards are sent.
                          </p>
                          <div className="runs-handoff">
                            <Button size="sm" variant="quiet" onClick={onDropCarried}>
                              {only === undefined
                                ? 'Identify every box instead'
                                : `Identify all of box ${only.box} instead`}
                            </Button>
                          </div>
                          <p className="run-step-fine">
                            Choosing another start above lets this selection go — it was made on the inventory screen
                            and only that screen can make another.
                          </p>
                        </div>
                      )
                    })()
                  )
                ) : null}

                {draft.start === 'run' ? (
                  <div className="runs-pick-said">
                    {runsTrouble === null ? null : <Notice tone="warn">{runsTrouble}</Notice>}
                    {runs === null ? (
                      <div className="bn-skeleton runs-pick-skel" aria-busy="true" />
                    ) : runs.length === 0 ? (
                      <EmptyState
                        icon="history"
                        title="No runs yet"
                        body="Identify a box first."
                      />
                    ) : (
                      <>
                        <label className="runs-field-inline">
                          <span>Run</span>
                          <select
                            className="bn-select"
                            value={draft.run ?? ''}
                            onChange={(event) => onDraft({ run: event.target.value === '' ? null : event.target.value })}
                          >
                            <option value="">Pick a run…</option>
                            {runs.map((row) => (
                              <option key={row.run} value={row.run}>
                                {row.run}
                                {runBoxLabel(row) === null ? '' : ` (${runBoxLabel(row)})`}
                              </option>
                            ))}
                          </select>
                        </label>
                        <p className="run-step-fine">
                          The cards that run answered, read again at the reading you choose next. Useful when a
                          photograph was replaced or a reading was too small to be trusted.
                        </p>
                      </>
                    )}
                  </div>
                ) : null}
              </div>

              {/* ---- the narrowing chips, on top of whichever start was chosen ---- */}
              <div className="runs-narrow" role="group" aria-label="Narrow the selection">
                <span className="bn-label runs-narrow-label">
                  <Icon name="filter" size={12} />
                  Narrow it
                </span>

                <label className="runs-field-inline">
                  <span>Game</span>
                  <select
                    className="bn-select"
                    value={draft.game ?? ''}
                    onChange={(event) => onDraft({ game: event.target.value === '' ? null : event.target.value })}
                  >
                    <option value="">Any game</option>
                    {(games ?? []).map((entry) => (
                      <option key={entry.key} value={entry.key}>
                        {entry.display}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="runs-field-inline">
                  <span>Section</span>
                  <select
                    className="bn-select"
                    disabled={sectionsOf === null}
                    value={draft.section === null ? '' : String(draft.section)}
                    onChange={(event) =>
                      onDraft({ section: event.target.value === '' ? null : Number(event.target.value) })
                    }
                  >
                    <option value="">Whole box</option>
                    {(sectionsOf?.sections_detail ?? []).map((row) => (
                      <option key={row.section} value={row.section}>
                        Section {row.section}
                        {row.name === null ? '' : ` (${row.name})`} with {plural(row.count, 'card')}
                      </option>
                    ))}
                  </select>
                </label>

                {/* THE SITTING IS SPENT AS A `since` BOUND, and that is a decision rather than a
                    gap: the server has no `sitting` term on purpose. Home clusters `captured_at`
                    into sittings in `app/src`, and a second clustering in Python would be a
                    second answer to the same question — so the screen reduces a sitting to the
                    bound it actually is. */}
                <label className="runs-field-inline">
                  <span>Photographed since</span>
                  <input
                    className="bn-input runs-since"
                    type="datetime-local"
                    value={draft.since ?? ''}
                    onChange={(event) => onDraft({ since: event.target.value === '' ? null : event.target.value })}
                  />
                </label>
                <Chip icon="clock" onClick={() => onDraft({ since: todayLocal() })}>
                  Today
                </Chip>
                {draft.since === null ? null : (
                  <Chip icon="x" onClick={() => onDraft({ since: null })}>
                    Any time
                  </Chip>
                )}

                {sectionsOf === null && draft.section === null ? (
                  <p className="run-step-fine runs-narrow-note">
                    Pick one box above to pick a section in it.
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}

          {/* --------------------------------------------------------- 2 · the reading */}
          {stage === 'read' ? (
            <div className="runs-composer-stage runs-composer-read" key="read">
              <div className="runs-reading">
                <div className="run-read">
                  <div className="run-read-head">
                    <span className="run-read-title">One reading for this press</span>
                    <span className="run-read-scope">{line}</span>
                  </div>
                  <Segmented<ReadingKey>
                    className="run-readings"
                    label="How these cards are read"
                    value={readingValue}
                    options={readingOptions}
                    onChange={(next) => {
                      if (next === 'custom') {
                        patchReading({ custom: true })
                        return
                      }
                      const option = READINGS.find((r) => r.key === next)
                      if (option !== undefined) {
                        patchReading({ custom: false, crop: option.crop, maxEdge: option.maxEdge })
                      }
                    }}
                  />
                  {reading.custom ? (
                    <div className="run-controls">
                      <label className="bn-check">
                        <input
                          type="checkbox"
                          checked={reading.crop}
                          onChange={(event) => patchReading({ crop: event.target.checked })}
                        />
                        Crop to the card
                      </label>
                      <label className="runs-field-inline">
                        <span>Max edge</span>
                        <input
                          className="bn-input bn-input-mono runs-edge"
                          type="number"
                          min={256}
                          max={4096}
                          step={100}
                          value={reading.maxEdge}
                          onChange={(event) => patchReading({ maxEdge: Number(event.target.value) })}
                        />
                        <span className="bn-muted">px</span>
                      </label>
                    </div>
                  ) : null}
                  {/* THE CLASS IS A TEST HOOK AND IS KEPT ON PURPOSE. `run-panel.spec.ts` reads
                      this line to assert that the reading is EXPLAINED before Check cost is
                      pressed rather than after it — D32's controls could not be read without
                      it — and a generic class here would make that assertion ambiguous the
                      moment a second fine line landed beside it, which is exactly what
                      happened. */}
                  <p className="run-step-fine runs-reading-says">
                    {reading.custom || readingMatch === null ? CUSTOM_SAYS : readingMatch.says}
                  </p>
                  {/* WHAT THE CART USED TO OFFER HERE, NAMED RATHER THAN MISSED: a reading per
                      drawer. Measured on this store, 12 of 15 runs share one `max_edge` and the
                      three that differ are three presses on three days — so a press that wants
                      two readings is two presses, which is what it always was in practice. */}

                </div>
              </div>

              <aside className="run-preview" aria-label="What this reading sends">
                <div className="run-preview-head">
                  <span className="bn-label">What this reading sends</span>
                  {preview === null ? null : (
                    /* The walk lives up here, above the frame, so it is on screen at every
                       viewport height — the arrow keys are only discoverable from it. */
                    <span className="run-preview-walk" role="group" aria-label="Walk the selection">
                      <Button size="sm" iconOnly icon="chevronLeft" onClick={() => setPreviewOffset((was) => was - 1)}>
                        The card before this one
                      </Button>
                      <span className="run-preview-count">
                        card {preview.offset + 1} of {count(preview.total)}
                      </span>
                      <Button size="sm" iconOnly icon="chevronRight" onClick={() => setPreviewOffset((was) => was + 1)}>
                        The card after this one
                      </Button>
                    </span>
                  )}
                </div>
                {previewTrouble !== null ? (
                  <Notice tone="warn">{previewTrouble}</Notice>
                ) : preview === null ? (
                  <div className="bn-skeleton runs-preview-skel" aria-busy="true" />
                ) : preview.sample.unreadable !== undefined || preview.sample.frame === undefined ? (
                  <p className="run-preview-fact">
                    {/* THE STORE KEY AND NOT A CARD NUMBER, on all four of this panel's figures.
                        `/pipeline/crop-preview` sends `{box, index}` and no slot, because what
                        it is describing is a PHOTOGRAPH — the same `(box, index)` `photoUrl` names
                        it by (D52) — and D58's countable number moves under that key every time a
                        card in front of this one leaves the box. Drawn as `Card 17` this panel
                        would name a different card than the one a hand counting into the drawer
                        reaches, so it draws what it actually has. */}
                    <span className="run-preview-slot">{storeKeyText(preview.sample.box, preview.sample.index)}</span>
                    <span>Can't decode — nothing sent.</span>
                  </p>
                ) : (
                  <div className="run-preview-card" aria-busy={previewBusy}>
                    <div className="run-preview-frame" onPointerMove={aimAt} onPointerLeave={() => setAim(null)}>
                      <img
                        className="run-preview-ghost"
                        /* THE SLOT ROUTE, BECAUSE THE PREVIEW HAS NO NAME TO OFFER (D172).
                           `POST /pipeline/runs/<name>/crop` answers with `{box, index}` and
                           nothing else — it describes a PHOTOGRAPH the detector just read off
                           disk, not a store record — so there is no `cid` on this payload to
                           address it by. */
                        src={photoUrl(preview.sample.box, preview.sample.index)}
                        alt=""
                        aria-hidden="true"
                        draggable={false}
                      />
                      {preview.sample.sent_image != null && (
                        <img
                          className="run-preview-sent"
                          src={preview.sample.sent_image}
                          alt={`${storeKeyText(preview.sample.box, preview.sample.index)}, as this reading sends it`}
                          draggable={false}
                          style={
                            preview.sample.rect != null && preview.sample.frame != null
                              ? {
                                  left: `${(preview.sample.rect[0] / preview.sample.frame[0]) * 100}%`,
                                  top: `${(preview.sample.rect[1] / preview.sample.frame[1]) * 100}%`,
                                  width: `${((preview.sample.rect[2] - preview.sample.rect[0]) / preview.sample.frame[0]) * 100}%`,
                                  height: `${((preview.sample.rect[3] - preview.sample.rect[1]) / preview.sample.frame[1]) * 100}%`,
                                }
                              : { left: 0, top: 0, width: '100%', height: '100%' }
                          }
                        />
                      )}
                      {preview.sample.rect != null && preview.sample.frame != null && (
                        <div
                          className="run-preview-cut"
                          style={{
                            left: `${(preview.sample.rect[0] / preview.sample.frame[0]) * 100}%`,
                            top: `${(preview.sample.rect[1] / preview.sample.frame[1]) * 100}%`,
                            width: `${((preview.sample.rect[2] - preview.sample.rect[0]) / preview.sample.frame[0]) * 100}%`,
                            height: `${((preview.sample.rect[3] - preview.sample.rect[1]) / preview.sample.frame[1]) * 100}%`,
                          }}
                        />
                      )}
                    </div>

                    <div
                      ref={detailRef}
                      className="run-preview-detail"
                      style={{
                        backgroundImage:
                          preview.sample.sent_image != null ? `url(${preview.sample.sent_image})` : undefined,
                        backgroundPosition: detailPosition,
                      }}
                      role="img"
                      aria-label={`${storeKeyText(preview.sample.box, preview.sample.index)} at full size, as this reading sends it`}
                    />
                    <p className="run-preview-fact">
                      <span>{aim === null ? 'Resting on the collector number' : 'Where you are pointing'} (1:1)</span>
                      {preview.sample.band_px != null && (
                        <span>
                          the number is {preview.sample.band_px[0]}×{preview.sample.band_px[1]} px as sent
                        </span>
                      )}
                    </p>
                    {preview.sample.band_absent != null && (
                      /* The server's own sentence names a module and a file; the fact it carries
                         is this one. */
                      <p className="run-step-fine">
                        No number band on this game&rsquo;s cards — point at the card above to read any part of it.
                      </p>
                    )}

                    <p className="run-preview-fact">
                      <span className="run-preview-slot">{storeKeyText(preview.sample.box, preview.sample.index)}</span>
                      {preview.sample.sent != null && (
                        <span>
                          sent at {preview.sample.sent[0]}×{preview.sample.sent[1]}, shown smaller here
                        </span>
                      )}
                      {preview.sample.method == null && <span>No card found — full photo sent.</span>}
                      {preview.sample.crop_refused != null && (
                        <span>Crop refused — full photo sent.</span>
                      )}
                    </p>
                    {preview.sample.crop_refused != null && (
                      <p className="run-step-fine">{preview.sample.crop_refused}</p>
                    )}

                    <p className="run-preview-hint">
                      <Kbd>←</Kbd>
                      <Kbd>→</Kbd> walk the selection
                    </p>
                  </div>
                )}
              </aside>
            </div>
          ) : null}

          {/* ------------------------------------------------------ 3 · the money moment */}
          {stage === 'quote' && quote !== null ? (
            <div className="runs-composer-stage runs-quote run-quote" key="quote">
              <div className="runs-quote-figure">
                <span className="bn-label">Estimated cost</span>
                <span className="runs-quote-money">{money(quote.total.estimate_usd)}</span>
                <span className="runs-quote-line">
                  <span>
                    <strong>{plural(quote.total.to_send ?? 0, 'card')}</strong> to send
                  </span>
                  <span>{count(quote.total.cache_hits)} already answered</span>
                  <span>{count(quote.total.photographs)} photographs</span>
                </span>
                <span className="runs-quote-line">
                  {/* `cards` IS THE SELECTION AND `to_send` IS THE INVOICE, and the two differing
                      is the cache doing its job — which on this store is the ordinary case, not
                      the exception. D33's rule is that the total is the number the operator
                      agrees to spend, and the old `boxes` figure was the least useful true number
                      available about a press over 2,535 cards in five drawers. */}
                  {plural(quote.total.cards, 'card')} in the selection
                </span>
              </div>

              {/* THE SERVER'S OWN SENTENCE, VERBATIM. `Selection.sentence()` composes it once for
                  the report, every refusal and this screen, because a press spelled one way here
                  and another in a refusal is two things an operator has to learn to read as
                  one. */}
              <div className="runs-quote-over">
                <span className="bn-label">This press is over</span>
                <p className="runs-quote-sentence">{quote.sentence}</p>
                <p className="run-step-fine">
                  {quote.scope === null
                    ? 'These cards are in more than one box.'
                    : quote.scope.whole_box
                      ? `The run will record all of ${boxLabel(
                          quote.scope.box,
                          boxes?.find((row) => row.box === quote.scope?.box)?.name,
                        )}.`
                      : `The run will record ${count(quote.scope.cards)} of ${boxLabel(
                          quote.scope.box,
                          boxes?.find((row) => row.box === quote.scope?.box)?.name,
                        )}'s cards.`}
                </p>
              </div>

              {partial === null ? null : (
                /* UNREACHABLE AND KEPT (`RunStartFailure`). A cart could half-start — `Popen`
                   failing on the fourth leg after three had started was an invoice for three
                   drawers reported as one failure — and one child cannot: it spawns or the
                   request refuses. The notice is one `length` check and costs nothing to keep,
                   and it no longer names a box because the failure has no drawer to name. */
                <Notice tone="danger" title={`${plural(partial.length, 'run')} did not start`}>
                  Nothing in this send was paid for. Press again.
                  {partial.map((row) => (
                    <div className="bn-notice-code runs-code-parts" key={row.code}>
                      <span>{row.code}</span>
                      <span>{row.sentence ?? row.message}</span>
                    </div>
                  ))}
                </Notice>
              )}

              {quote.claimed !== null ? (
                /* THE COURTESY HALF OF THE MONEY GUARD, AND THE WHOLE OF IT SINCE THE BOX-LEVEL
                   `busy_run` WENT (D174). That check compared BOX numbers and this route no
                   longer takes one; a claim is per CARD, which is the one vocabulary that has an
                   answer for every press. The sentence is the server's — `store/submissions.py`
                   composes it for both refusal sites — and a third spelling here would be a third
                   message to learn. */
                <Notice tone="warn" title="Some of these cards are already being paid for">
                  {quote.claimed.sentence}. Watch that run, or release its claim if its holder is gone.
                  <div className="bn-notice-code runs-code-parts">
                    <span>{plural(quote.claimed.cards, 'card')}</span>
                    <span>
                      {quote.claimed.runs.length > 0 ? quote.claimed.runs.join(', ') : quote.claimed.receipts.join(', ')}
                    </span>
                  </div>
                </Notice>
              ) : quote.total.to_send === 0 ? (
                <Notice tone="ok" title="Nothing to send">
                  All {plural(quote.total.cards, 'card')} in this selection are already answered — nothing to spend.
                </Notice>
              ) : (
                <>
                  {overNotice || raised !== null ? (
                    /* THE SPEND NOTICE, AND IT IS A SENTENCE RATHER THAN A GATE (the owner's
                       ruling, 2026-09-12: *"Give me settings if I can have them, but if I want to
                       run everything, then I get to run everything."*). The confirm below is
                       untouched — not disabled, not hidden, not moved — and the only thing this
                       block does is say so out loud and offer a way to stop being asked.

                       IT STAYS ON SCREEN AFTER THE RAISE, carrying the result instead of the
                       question (D118): a block that vanished on its own press would pull the
                       spend button up under the finger that just pressed it. */
                    <Notice
                      tone={raised === null ? 'warn' : 'ok'}
                      title={
                        raised === null
                          ? `More than the ${money(notice)} this device asks about`
                          : `Noted — nothing under ${money(raised)} will ask again`
                      }
                    >
                      {raised === null ? (
                        <div className="runs-spend-row">
                          <span>This send is {money(estimate)}.</span>
                          <Button
                            size="sm"
                            variant="quiet"
                            onClick={() => raiseNotice(coverFor(estimate ?? notice))}
                          >
                            Stop asking under {money(coverFor(estimate ?? notice))}
                          </Button>
                        </div>
                      ) : (
                        <span>Remembered on this browser. Change the figure below to be asked sooner.</span>
                      )}
                    </Notice>
                  ) : null}

                  <div className="runs-quote-confirm">
                    <Button
                      variant="primary"
                      size="xl"
                      icon="zap"
                      className="run-button-money"
                      busy={busy === 'start'}
                      disabled={busy !== null}
                      onClick={() => void doStart()}
                    >
                      {`Spend ${money(quote.total.estimate_usd)} and identify ${count(quote.total.to_send)} cards`}
                    </Button>
                    <span className="runs-quote-fine">
                      One run. Identification takes minutes to hours and keeps going if you close this tab.
                    </span>
                    {/* THE SETTING ITSELF, ALWAYS ON SCREEN AND NEVER ONLY INSIDE THE WARNING —
                        otherwise the figure could be raised and never lowered again. */}
                    <label className="runs-field-inline runs-spend-set">
                      <span>Ask me above</span>
                      <span className="bn-muted">$</span>
                      <input
                        className="bn-input bn-input-mono runs-spend-input"
                        type="number"
                        min={0.01}
                        step={0.5}
                        value={notice}
                        onChange={(event) => {
                          const next = Number(event.target.value)
                          if (!Number.isFinite(next) || next <= 0) return
                          setNotice(next)
                          setRaised(null)
                          rememberSpendNotice(next)
                        }}
                      />
                    </label>
                  </div>
                </>
              )}

              {(quote.total.cache_hits ?? 0) > 0 && (
                <p className="run-step-fine runs-quote-cache">
                  Already-answered cards keep their first reading.
                </p>
              )}

              <div className="runs-quote-consoles">
                <button
                  type="button"
                  className="runs-disclose"
                  aria-expanded={showPreflight}
                  onClick={() => setShowPreflight((v) => !v)}
                >
                  <Icon name="chevronDown" size={14} />
                  What the preflight printed
                </button>
                {showPreflight ? (
                  <>
                    {/* ONE WELL, WHERE THE CART HAD ONE PER LEG. There is one command and one
                        console: `_preflight` shells `identify --dry-run` once over the whole
                        selection, so a press over five drawers is one dry run rather than five
                        each re-walking a drawer. */}
                    <LogWell text={quote.console} label="Preflight" maxHeight={220} />
                    <p className="run-step-fine">
                      Scanned under {quote.capture_dirs.join(', ')}
                      {quote.exit_code === 0 ? '' : ` (exit ${quote.exit_code})`}
                    </p>
                  </>
                ) : null}
              </div>
            </div>
          ) : null}

          {/* --------------------------------------------------------------- 4 · receipt */}
          {stage === 'started' && started !== null ? (
            <div className="runs-composer-stage runs-receipt" key="started">
              <span className="runs-receipt-art">
                <Icon name="check" size={28} strokeWidth={2.25} />
              </span>
              <h3 className="runs-receipt-title">
                {started.runs.length === 1 ? 'The run has started' : `${started.runs.length} runs have started`}
              </h3>
              <p className="runs-receipt-line">
                {plural(started.cards ?? 0, 'card')} sent to be read (<strong>{money(started.estimate)}</strong>)
              </p>
              <ul className="runs-receipt-runs">
                {started.runs.map((row) => (
                  <li key={row.run}>
                    {/* `scope` IS NULLABLE AND THE RECEIPT MUST NOT CRASH ON IT. A press whose
                        cards are in more than one drawer records no drawer at all, which is an
                        ordinary outcome of a store-wide press rather than a fault — so the
                        selection's own words stand in where there is no box to label. */}
                    <span className="runs-receipt-box">{runLabel(row, boxes) ?? `${plural(row.cards, 'card')}`}</span>
                    <span className="bn-mono runs-receipt-run">{row.run}</span>
                  </li>
                ))}
              </ul>
              {partial === null ? null : (
                <Notice tone="danger" title={`${plural(partial.length, 'run')} did not start`}>
                  Nothing in that send was paid for. Check the cost again to start it.
                  {partial.map((row) => (
                    <div className="bn-notice-code runs-code-parts" key={row.code}>
                      <span>{row.code}</span>
                      <span>{row.sentence ?? row.message}</span>
                    </div>
                  ))}
                </Notice>
              )}
              <p className="run-step-fine runs-receipt-fine">
                Identification takes minutes to hours and keeps running if you close this tab. The run is open
                beside the list and re-reads itself while it is live.
              </p>
            </div>
          ) : null}
        </div>

        <footer className="runs-composer-foot">
          {stage === 'select' ? (
            <>
              <span className="runs-composer-note">{line}</span>
              <Button variant="ghost" onClick={close}>
                Cancel
              </Button>
              <Button variant="primary" iconRight="arrowRight" disabled={!scoped} onClick={() => setStage('read')}>
                Next: photos
              </Button>
            </>
          ) : null}
          {stage === 'read' ? (
            <>
              <Button variant="ghost" icon="arrowLeft" onClick={() => setStage('select')}>
                Cards
              </Button>
              <span className="runs-composer-note">{line}</span>
              <Button
                variant="primary"
                icon="dollar"
                busy={busy === 'quote'}
                disabled={!scoped || busy !== null}
                onClick={() => void doQuote()}
              >
                Check cost
              </Button>
            </>
          ) : null}
          {stage === 'quote' ? (
            <>
              <Button variant="ghost" icon="arrowLeft" onClick={() => setStage('read')}>
                Photos
              </Button>
              <span className="runs-composer-note">{line} (quoted for exactly these cards)</span>
              <Button variant="ghost" onClick={close}>
                Not now
              </Button>
            </>
          ) : null}
          {stage === 'started' ? (
            <>
              <span className="runs-composer-note">
                The quote is spent; check the cost again before identifying more.
              </span>
              <Button variant="primary" icon="eye" onClick={close}>
                Watch the run
              </Button>
            </>
          ) : null}
        </footer>
      </div>
    </>,
    document.body,
  )
}

/** What a started run is CALLED on the receipt: its drawer where it recorded one, and null where
 *  it did not. `boxLabel` is reached only through a real box number, which is the whole of what
 *  the nullable `scope` costs a reader. */
function runLabel(row: RunStartedRun, boxes: readonly BoxRecord[] | null): string | null {
  if (row.scope === null) return null
  return boxLabel(row.scope.box, boxes?.find((record) => record.box === row.scope?.box)?.name)
}

/** The preview's own key. A function so the debounce effect depends on a string rather than on
 *  the `send` object, whose identity moves with every render of its parents. */
function showingKey(sendKey: string): string {
  return sendKey
}
