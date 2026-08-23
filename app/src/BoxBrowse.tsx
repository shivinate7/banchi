import { useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent } from 'react'
import { isEditableTarget } from './keys'
import type { BoxRecord, InventoryCard } from './types'
import type { Failure } from './server'
import {
  describeFailure,
  positionLabel,
  placeSentence,
  getBoxes,
  getInventory,
  photoUrl,
  reshootPhoto,
  newCaptureId,
} from './server'
import { BoxOps, RegisterBox } from './BoxOps'
import { SearchField } from './SearchField'
import { useSearch } from './useSearch'
import './BoxBrowse.css'

/* THE BROWSE — box, then section, then card. One of `#/inventory`'s two ways in (D31).
 *
 * THIS FILE WAS `PullPreview.tsx` AT `#/pull` AND IS THE SAME WALK, taken forward rather than
 * rewritten. The owner's words are in D31: three routes rendered the same 767 records and
 * "read as separate instances of one thing", and the one question a person actually arrives
 * with — what is in this box, and can I click it — was answerable on the screen named after a
 * fulfilment errand and nowhere else. So the route is gone and the walk is now what the
 * inventory's Browse mode renders. Everything the walk had been tuned into keeping — sticky
 * section headers, the segmented strip, one-line rows, the deep keys scoped to the list, the
 * detail panel with the photograph — is unchanged, because it was the best-tested navigation
 * in the app and rewriting it would have thrown that away to arrive back at it.
 *
 * WHAT ACTUALLY CHANGED, and it is one idea: THE STRIP SELECTS RATHER THAN JUMPS. It used to
 * scroll one continuous walk of every card in the store to the first row of a box; it now
 * chooses which box the walk is OF. The reason is the browse's own shape — D31 puts the box
 * operations on the box header, and a header that names one box cannot sit over a list holding
 * four. It is also the density answer: box 2 alone is 544 cards, so a walk of all 767 is a
 * scroller whose position tells you nothing, which is the complaint that started this work.
 * The section headers lost their `Box N ·` prefix in the same move — the box is named once,
 * above the list, by the panel that can also rename and seal it.
 *
 * THE RE-SHOOT CONTROL CAME WITH IT AND MAY NOT BE DROPPED. D26 put it on the pull preview
 * deliberately — "the screen whose whole job is looking at one stored photo beside its
 * position, so the moment a bad photo is discovered is the moment the remedy is already on
 * screen" — and D31 is explicit that the argument is about a detail panel showing one card's
 * photograph rather than about a URL, so it transfers intact and a merge that lost it would
 * have broken D26. It is below, unchanged, at `ReshootControl`.
 *
 * THE ONE WRITE THIS FILE MAKES ABOUT A CARD, AND ITS WHOLE EXTENT: replacing a photograph.
 * D26's re-shoot half — new bytes and a rebuilt sidecar at the same position, record
 * untouched, label unchanged, allocator never involved. Nothing else here writes a card;
 * mark-sold and retire belong to the search half of this screen. `BoxOps` writes the BOX,
 * which is a different object and says so.
 *
 * NO CONFIRM DIALOG, AND THE RE-SHOOT IS IRREVERSIBLE — both at once, deliberately, and the
 * reasoning is capture-undo's (docs/DESIGN.md) transposed: the old bytes are gone, not
 * archived, but the CARD is still in its slot, so the remedy for a wrong re-shoot is another
 * re-shoot. What bounds the loss on undo — the card still in your hand — is here the card
 * still in its box. A dialog would tax every correct replacement to soften a mistake that has
 * a two-tap repair.
 *
 * The photo comes from `GET /photo/<box>/<index>`, which is D6's route and the reason that
 * route exists at all: the review queue requires it and the pull modal reuses it.
 *
 * Owner-side, so density is fine and docs/DESIGN.md's Fulfillment floors do not bind.
 * They bind on 7b's pull modal, which is a different screen for a different person;
 * borrowing them here would make this screen look like his and set the expectation that
 * it is safe for him to use, which it is not — it lists every card in every state, speaks
 * the pipeline's vocabulary, and now carries a control that destroys a photograph.
 */

/* The position label is READ off the wire and never composed here, and the rule now lives in
 * `server.ts:positionLabel` — this file wrote it, the inventory view copied it verbatim, and
 * one rule about one field is one function. The whole argument went across with it, including
 * the part this screen learned the hard way: an earlier draft ported the arithmetic and D10's
 * 25-cards-per-divider constant into TypeScript, which is one divider size living in two
 * languages with nothing keeping them in step — and of the two answers, the one on screen is
 * the one a person walks to a box with.
 *
 * What stayed here is the fallback at the call sites below, which is this screen's decision
 * rather than the rule's: a row with no label shows its store key with `no label` in front of
 * it. Recomputing the label locally would trade a visible gap for an invisible disagreement,
 * and only one of those sends someone to the wrong slot.
 */

/* The inventory arrives as a map keyed `"3/1"`. The key is kept for identity and React,
 * and shown verbatim in the one case where a row carries no label — never parsed into a
 * position: a store key and a physical location are two different facts that agree for the
 * first 25 cards in a box and diverge from card 26 on, where `3/26` is Section 2, Card 1. */
type Row = { key: string; card: InventoryCard }

/* Box-walk order — box, then index. The same order `store/queues.py:sort_key` falls back
 * to and the order the cards physically sit in, so reading down this list is walking the
 * box. Rejected: newest first, which is the order you want while capturing and the wrong
 * one while checking a run against the boxes on the desk. */
function rowsOf(cards: Record<string, InventoryCard>): Row[] {
  return Object.entries(cards)
    .map(([key, card]) => ({ key, card }))
    .sort((a, b) => a.card.box - b.card.box || a.card.index - b.card.index)
}

/* The identity every control below preserves: `visible` is always a subsequence of
 * `rowsOf`'s answer. The search narrows it, the sections partition it, the box strip
 * indexes it, and every key walks it — one order, stated once, so no two controls on this
 * screen can disagree about what comes next. The constant is module-level so an empty
 * answer keeps one identity across renders and the effects hanging off `visible` do not
 * re-arm while the inventory is still loading. */
const NO_ROWS: Row[] = []

// ------------------------------------------------------------------ the walk, in sections

/* WHICH SHELF A ROW IS ON — the thing the strip selects, and the scope of one walk.
 *
 * A box number for an ordinary card; `pooled` for a card whose game says `located: false`
 * (D24 — a count, not a location, so its `box` is a store key and putting it under a box
 * number would make the strip promise a shelf); `unplaced` for the record whose box will not
 * coerce, which `do_inventory` leaves undecorated and `GET /status` reports. Three shelves and
 * not two, because a design fact and a fault must never share a cell.
 */
type Shelf = number | 'pooled' | 'unplaced'

function shelfOf(row: Row): Shelf {
  if (isPooled(row.card)) return 'pooled'
  const box = row.card.box
  if (typeof box !== 'number' || Number.isNaN(box)) return 'unplaced'
  return box
}

/** What a shelf's cell says on the strip, and what the box header says above the walk. */
function shelfLabel(shelf: Shelf): string {
  if (shelf === 'pooled') return 'pooled'
  if (shelf === 'unplaced') return 'no box'
  return String(shelf)
}

/* Every shelf the current walk touches, boxes first and in the walk's own order.
 *
 * BUILT FROM THE SEARCH-FILTERED ROWS rather than from the whole store, which is the rule the
 * jump strip already followed: under a query the strip offers only shelves that still hold a
 * match, so a cell can never lead to an empty list. The two non-numeric shelves go last and
 * only when something is actually on them — a cell for a condition nothing is in is chrome
 * that has stopped being true, the same rule the key chips follow.
 */
function shelvesOf(rows: Row[]): Shelf[] {
  const out: Shelf[] = []
  let pooled = false
  let unplaced = false
  for (const row of rows) {
    const shelf = shelfOf(row)
    if (shelf === 'pooled') pooled = true
    else if (shelf === 'unplaced') unplaced = true
    else if (!out.includes(shelf)) out.push(shelf)
  }
  if (pooled) out.push('pooled')
  if (unplaced) out.push('unplaced')
  return out
}

/* Which stretch of one shelf's walk a row belongs to, worded as its sticky header will say it.
 *
 * NO `Box N ·` PREFIX ANY MORE, and that is the merge's doing rather than a trim: the walk is
 * scoped to one shelf now and the box is named once above it, by a panel that can also rename
 * and seal it. Repeating the box number down every header would spend most of a narrow
 * column's width restating the one fact that cannot change while you are reading.
 *
 * Composed from the server's own decorations — the label rule at the top of this file forbids
 * position ARITHMETIC here, and this does none: `section` is a number the server sent, and the
 * span is `Place.section_start`/`section_end`, which is the store's own answer to where this
 * section begins and ends. A section with no end is drawn as open rather than filled in with
 * the box total, exactly as the layout table draws it: the two mean different things, and the
 * second is a claim about where a divider is.
 *
 * A pooled row groups under the pooled fact and a bare record under the fault, so a header
 * never claims a location the rows beneath it do not have.
 */
function sectionTitleOf(row: Row): string {
  if (isPooled(row.card)) {
    return `Pooled · ${row.card.place?.game_display ?? row.card.game ?? 'cards'}`
  }
  if (row.card.section === undefined) return 'No position label'

  const start = row.card.place?.section_start
  const end = row.card.place?.section_end
  if (typeof start !== 'number') return `Section ${row.card.section}`
  return typeof end === 'number'
    ? `Section ${row.card.section} · #${start}–#${end}`
    : `Section ${row.card.section} · #${start} onward`
}

type Section = { key: string; title: string; first: Row; rows: Row[] }

/* Run-length over the walk, deliberately not a Map keyed on title: the list's order is
 * `rowsOf`'s and a grouper must not invent a second one. Whatever order the rows arrive in
 * survives exactly — a keyed Map would quietly merge two stretches that something (a
 * record whose box is a string, a future sort) had separated, and the merged header would
 * lie about what sits under it. Keyed by the title plus the first row's key, so React
 * identity holds even when two separated stretches share a title. */
function sectionsOf(rows: Row[]): Section[] {
  const out: Section[] = []
  for (const row of rows) {
    const open = out[out.length - 1]
    const title = sectionTitleOf(row)
    if (open !== undefined && open.title === title) open.rows.push(row)
    else out.push({ key: `${title} @ ${row.key}`, title, first: row, rows: [row] })
  }
  return out
}

/* What a row's left cell says. Under a section header the answer is the slot alone — `17`
 * beneath `BOX 1 · SECTION 2` — read off the server's `card` decoration, never parsed out
 * of the label string: the header and the slot are two server facts drawn at two sizes,
 * and D10's divider arithmetic keeps living in one language. The fallbacks are the old
 * two-line row's, unchanged: a pooled card gets its pooled words, a bare record its store
 * key with `no label` in front, and a row that somehow carries a label without a slot
 * shows the label whole rather than a guess. */
function rowSlot(row: Row): string {
  if (row.card.card !== undefined) return String(row.card.card)
  const label = positionLabel(row.card)
  if (label !== null) return label
  return isPooled(row.card) ? pooledText(row.card, row.key) : `no label · ${row.key}`
}


// -------------------------------------------------------------- stepping through the list

/* Left and Right move the selection one card, in the order `rowsOf` already put them in and
 * no other. The owner asked for this by name — "fast nav" — and what makes it fast is not the
 * binding but the two properties below: a held key repeats, and the ends stop.
 *
 * NOTHING HERE WRITES, and adding a key does not bend the look-only rule in this file's
 * header. A selection change is the same non-event a click on a row already was; the keys buy
 * a hand back, not a new power.
 *
 * ONE TABLE, TWO CONSUMERS: the handler reads `key` and `delta`, and the chips in the header
 * draw `label`. ReviewQueue.tsx pairs each key with its label constant for this reason, and
 * the reason is worth repeating — a screen that can advertise a key nothing listens for will
 * eventually do it, and that failure is invisible until someone presses the key.
 *
 * HOME AND END WERE DECLINED AT WINDOW SCOPE, AND ARE NOW BOUND WHERE THE DECLINE SAID
 * THEY BELONG. The paragraph this replaces refused them because at window scope those keys
 * are the page's own — End is how you reach the bottom of the facts panel — and then named
 * its own fix: "Home and End bound on the list with the chips moved onto it — never a
 * wrap". That is what is built, for all four deep keys: PageUp, PageDown, Home and End are
 * a React handler ON the list element, so holding focus IS the scope and there is no
 * listener to tear down, and the chips advertising them sit under the list saying the
 * condition out loud. The cost the old paragraph feared — one key doing two things
 * depending on where focus happens to be — is conceded rather than argued away: it is paid
 * where the browser itself set the precedent, since PageDown already scrolls whichever
 * pane holds focus, and a chip that names the scope is what keeps the rule visible rather
 * than diagnosed. Still never a wrap, and every end still stops.
 */
const STEPS = [
  { key: 'ArrowLeft', label: '←', delta: -1 },
  { key: 'ArrowRight', label: '→', delta: 1 },
] as const

/* The deep keys, list-scoped — the ruling above. Same table shape as STEPS and for the
 * same reason: the handler reads `key`, the chips under the list draw `label`, and a
 * screen that can advertise a key nothing listens for will eventually do it.
 *
 * PageUp goes to the top of the CURRENT section first and to the previous one only from
 * there. The pair moves by BOUNDARY — the same boundaries the sticky headers draw, so the
 * key does what the picture says — and from the middle of a section the nearest boundary
 * backwards is that section's own start; skipping it would overshoot the header on
 * screen. */
const SECTION_KEYS = [
  { key: 'PageUp', label: 'PgUp', delta: -1 },
  { key: 'PageDown', label: 'PgDn', delta: 1 },
] as const

/* First and last of the CURRENT filter, not of the whole store — Home under a query lands
 * on the first MATCH, which is what "the beginning" means while a filter is on. */
const EDGE_KEYS = [
  { key: 'Home', label: 'Home', last: false },
  { key: 'End', label: 'End', last: true },
] as const


/* `describeFailure` and `Failure` LIVED HERE and moved to server.ts on 2026-08-13, beside
 * the `ServerError` they destructure. This file's copy was the original and the argument in
 * its docstring travelled with it whole — including the reason it does not offer `make
 * server`, which this screen learned by getting it wrong first. Two later screens had copied
 * it byte for byte, and both of those comments named server.ts as the destination; the third
 * copy is what made the move due. */

/* A POOLED CARD — the owner's ruling that a code card is a count, not a location
 * (`pipeline/games.py`'s `located` flag; "Code cards are pooled inventory, not located" in
 * docs/DECISIONS.md). The server sends its row with no flat label and a `place` block
 * carrying `located: false` plus the game's display name, so this screen can tell the
 * design fact from the fault it already draws a panel for: a row whose box will not coerce
 * arrives with no `place` at all. `!== false` keeps an older server's rows — no flag
 * anywhere — reading as located, which they all are. */
function isPooled(card: InventoryCard): boolean {
  return card.place?.located === false
}

/** The row line and the machine line for a pooled card, one composer for both call sites.
 *  The display name is the server's stamp off the registry; `pooled ·` in front of the
 *  store key so `5/2` cannot read as a position — the same trick the no-label fallback
 *  below plays with `no label ·`. */
function pooledText(card: InventoryCard, key: string): string {
  return `${card.place?.game_display ?? card.game ?? 'pooled'} · pooled · ${key}`
}

type Detail = { label: string; value: string; mono: boolean }

/* What is shown beside the photo, and the reason it is more than the position.
 *
 * §7 asks for the photo and the label. `state` earns its line anyway: it is the other
 * half of the Gate B question — the photo proves the capture landed, the state proves
 * whether anything downstream has touched it. The rest are the fields a run is debugged
 * with, and this is the screen open while it is being debugged.
 *
 * A card's name is a thing a human reads, so it takes the body face; everything else is a
 * value being compared against something, so it takes the utility face. That is
 * docs/DESIGN.md's mono-carries-all-metadata rule applied one field at a time rather than
 * one panel at a time.
 */
function detailsOf(card: InventoryCard): Detail[] {
  return [
    { label: 'Card', value: card.name ?? 'not identified yet', mono: card.name === null },
    { label: 'Number', value: collectorNumber(card), mono: true },
    // The record's own game claim, verbatim. Null means written before the field existed
    // — the pipeline reads that as pokemon, and saying "not recorded" is the honest form
    // of the same fact. Earns its line the day boxes are mixed: it is what explains why
    // the panel above says pooled, or does not.
    { label: 'Game', value: card.game ?? 'not recorded', mono: true },
    { label: 'State', value: card.state, mono: true },
    { label: 'Captured', value: card.captured_at ?? 'not recorded', mono: true },
    { label: 'Set hint', value: card.set_hint ?? 'none', mono: true },
    { label: 'Finish', value: card.metadata_finish ?? 'none recorded', mono: true },
  ]
}

/* Shown as the model returned it, unpadded. `pipeline/join.py:join_key` zero-fills to
 * three digits to match the export's `Number` column, and doing that here would put a
 * string on screen that nothing in the run ever said — which is the wrong trade on the
 * screen someone opens to find out what the run actually said. */
function collectorNumber(card: InventoryCard): string {
  if (card.number === null) return 'none'
  return card.printed_total === null ? card.number : `${card.number}/${card.printed_total}`
}

export function BoxBrowse() {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  /* WHICH SHELF THE WALK IS OF, or null before the first read has said which shelves exist.
   * The strip writes it and the effect below keeps it honest against the current filter.
   *
   * NOT PERSISTED, and worth one line because two neighbours in this app are. `useCamera.ts`
   * remembers a device and a rotation and D27 lets the capture screen remember its claims —
   * both because they describe THIS RIG and would be wrong shared. Which box you were last
   * looking at describes a minute of reading, not the rig, and a browse that reopened on box
   * 95 because that is where a different question ended would be a screen arguing with the
   * person who just opened it. */
  const [shelf, setShelf] = useState<Shelf | null>(null)

  /* The box registry, for the panel above the walk — `GET /boxes`, the one route that renders
   * a box's own layout. Empty until it answers and empty forever if it never does: the walk
   * does not depend on it, so a dead `/boxes` costs the header and nothing else. Kept as the
   * raw list rather than a map because it is four rows today and thirty at worst, and a
   * `.find` over thirty is not a data structure worth having. */
  const [boxRecords, setBoxRecords] = useState<readonly BoxRecord[]>([])
  /* The key whose photo 404'd, not a boolean: an `onError` from the previously selected
   * card can land after the selection has moved, and a boolean would blame the wrong
   * card for a missing file. */
  const [photoAbsent, setPhotoAbsent] = useState<string | null>(null)
  const [reloads, setReloads] = useState(0)
  /* Each re-shot card's NEW capture id, by row key — the cache nonce PhotoPanel appends
   * after a replacement, and nothing else. The id rather than a counter because it
   * already names the exact photograph the screen expects, so a `?reshot=<id>` in a
   * network log is self-explaining. Kept across reloads deliberately: the URL is the
   * same stable one, and the bytes behind it are still the ones this id names. */
  const [reshot, setReshot] = useState<Record<string, string>>({})
  /* The key of the replacement in flight, or null — one at a time, the same rule every
   * write in this app follows: `Store.write()` takes the file lock per call. */
  const [reshootBusy, setReshootBusy] = useState<string | null>(null)
  /* A refusal PAIRED WITH ITS CARD, not floated loose: stepping to the next card must
   * not carry the previous card's refusal under a photo it says nothing about. */
  const [reshootFailure, setReshootFailure] = useState<{ key: string; failure: Failure } | null>(
    null,
  )
  const listRef = useRef<HTMLUListElement | null>(null)
  /* The key a box-chip jump wants scrolled to the TOP of the scroller, or null for every
   * ordinary selection change. One-shot; the scroll effect consumes it. `block: 'nearest'`
   * is right for a step and wrong for a jump — after two hundred rows it parks the landing
   * at the bottom edge, which shows the END of the box before the one just asked for. */
  const jumpRef = useRef<string | null>(null)

  /* THE SEARCH IS THE SERVER'S MATCHER FILTERING THIS SCREEN'S OWN LIST — neither of the
   * two shapes already in the app, and argued against both. Inventory.tsx renders the
   * search RESPONSE, because `GET /search` carries facts `GET /inventory` does not; this
   * screen needs none of them — its rows are already here, labelled and ordered, and what
   * it lacks is only WHICH of them the owner means. So the answer is read for its copy
   * KEYS and nothing else, and the walk keeps its own order and its own rendering. The
   * other obvious shape — a client-side substring over `name` — was declined harder:
   * `do_search` matches six fields (name, number, the zfilled join key, SKU, set hint,
   * note), and the note is the only handle a card the pipeline never identified has. A
   * second, weaker matcher here would make `#/pull` and `#/inventory` answer the same
   * query differently, and nothing anywhere would say so.
   *
   * NO `autoFocus`, WHERE Inventory PASSES IT — a screen's judgement, exactly as
   * SearchField's prop says. That screen is opened to type; this one is opened to WALK,
   * and a field holding focus on arrival is a field eating the arrow keys the header
   * advertises (they guard on `isEditableTarget`). `/` reaches the field from anywhere. */
  const { query, setQuery, results, loading, failure: searchFailure } = useSearch()
  const searching = query.trim() !== ''

  /* Every key the answer names, flattened — membership is the one thing this screen reads
   * off it. Copies of sold and retired cards are in there too, which is right: the walk
   * lists every card in every state, and a search that could not find a sold card would
   * be a search that cannot answer "where was it". */
  const matched = useMemo(() => {
    if (results === null) return null
    const keys = new Set<string>()
    for (const group of results.groups) for (const copy of group.copies) keys.add(copy.key)
    return keys
  }, [results])

  /* Filtered only when there is an answer to filter BY. While the first answer is still
   * owed — debounce, flight — the walk stays whole rather than blanking on every
   * keystroke: Inventory.tsx's rule ("a list that blanks is worse to type against than
   * one that lags by 200ms and says so") applied to a list that exists before the query
   * does; the `Looking.` line is what says so. A FAILED search also leaves the whole walk
   * standing, under the failure panel: an empty list would claim "no card matches", which
   * is an answer, and a failure is precisely not one. */
  const inQuery = useMemo(() => {
    if (rows === null) return NO_ROWS
    if (!searching || matched === null) return rows
    return rows.filter((row) => matched.has(row.key))
  }, [rows, searching, matched])

  /* The shelves the query still reaches, and then the one shelf being walked. TWO STAGES AND
   * NOT ONE, because they answer different questions: the strip has to offer every shelf the
   * query matches (or a match in another box would be invisible with nothing saying so), and
   * the list has to show one shelf's worth (or the header above it would name a box the rows
   * do not all belong to). `visible` stays the name every control below already walks. */
  const shelves = useMemo(() => shelvesOf(inQuery), [inQuery])

  const visible = useMemo(() => {
    if (shelf === null) return NO_ROWS
    return inQuery.filter((row) => shelfOf(row) === shelf)
  }, [inQuery, shelf])

  const sections = useMemo(() => sectionsOf(visible), [visible])

  /* The box row for the shelf being walked, or null — the header draws `BoxOps` only for a
   * NUMBERED shelf that the registry actually knows. A box a card names but `GET /boxes` has
   * not answered for gets no panel rather than an invented one: the operations it would offer
   * write to a record that is not there. */
  const shelfBox = useMemo(() => {
    if (typeof shelf !== 'number') return null
    return boxRecords.find((record) => record.box === shelf) ?? null
  }, [boxRecords, shelf])

  /* The re-shoot, from a picked file to the server. The base64 the wire wants is the
   * data-URL's payload — sliced at the first comma rather than split, and RAW, no
   * `data:` prefix, exactly as `capture()` documents: the server refuses the prefixed
   * shape loudly rather than letting two spellings spread.
   *
   * A FRESH CAPTURE ID PER PICK, and that is safe HERE in a way it is not on the capture
   * screen. There the id must survive a retry because a replay with a new id burns an
   * index; a re-shoot allocates nothing, so the lost-response worst case is the same
   * bytes written to the same position twice with one extra history line. Holding the id
   * across a retry would buy machinery, not safety.
   *
   * On success: remember the id as this card's cache nonce, then re-read the inventory —
   * the record's `photo` and `capture_id` changed server-side, the loader keeps the
   * selection, and it also resets `photoAbsent`, which is how a card whose photo file
   * was LOST comes back to life when a re-shoot gives the route bytes to serve again. */
  const beginReshoot = (row: Row, file: File) => {
    setReshootBusy(row.key)
    const reader = new FileReader()
    reader.onload = () => {
      const url = String(reader.result)
      const imageBase64 = url.slice(url.indexOf(',') + 1)
      const captureId = newCaptureId()
      reshootPhoto(row.card.box, row.card.index, imageBase64, captureId)
        .then(() => {
          setReshot((held) => ({ ...held, [row.key]: captureId }))
          setReshootBusy(null)
          setReshootFailure(null)
          setReloads((n) => n + 1)
        })
        .catch((err: unknown) => {
          setReshootBusy(null)
          /* Verbatim, owner screen: `card_sold` and `card_retired` should be unreachable
           * (the control is not drawn for either state), but a second device can move a
           * card between this screen's read and the press, and the server's message
           * names the way back better than anything composed here could. */
          setReshootFailure({ key: row.key, failure: describeFailure(err) })
        })
    }
    reader.onerror = () => {
      setReshootBusy(null)
      setReshootFailure({
        key: row.key,
        failure: describeFailure(reader.error ?? new Error('the picked file could not be read')),
      })
    }
    reader.readAsDataURL(file)
  }

  useEffect(() => {
    // StrictMode runs effects twice in dev, and a slow first response can land after the
    // second one. The flag makes the late arrival a no-op rather than a flicker.
    let live = true
    /* `.then(ok).catch(fail)` AND NOT `.then(ok, fail)`. The two-argument form does not cover
     * its own success handler, so anything thrown while walking the answer — `rowsOf` over a
     * body with no `cards`, which is what an older or wrong server returns — becomes an
     * unhandled rejection: no failure panel, no Reload to press, and the screen stuck on
     * "Reading the inventory." Fulfillment.tsx watched exactly that happen for a morning and
     * fixed itself; this file kept the shape for another ten days, which is the argument for
     * the eslint rule in `app/eslint.config.js` rather than for a fourth copy of this comment.
     * With `.catch` a body this screen cannot read fails the same way a dead server does. */
    getInventory()
      .then((inventory) => {
        if (!live) return
        const next = rowsOf(inventory.cards)
        setRows(next)
        setFailure(null)
        setPhotoAbsent(null)
        /* Keep the selection across a reload when the card is still there. An undo on the
         * capture screen deletes the newest card outright — D10, no tombstone — so a key
         * held blindly would render an empty panel that reads as a bug rather than as the
         * deletion it is. */
        setSelected((prev) =>
          prev !== null && next.some((row) => row.key === prev) ? prev : (next[0]?.key ?? null),
        )
      })
      .catch((err: unknown) => {
        if (!live) return
        setRows(null)
        setFailure(describeFailure(err))
      })
    return () => {
      live = false
    }
  }, [reloads])

  /* THE BOX REGISTRY, on the same counter as the inventory read and allowed to fail without
   * anybody hearing about it — `Inventory.tsx` argues the shape at length for its own layout
   * read and every word of it holds here. The walk, the strip, the rows and the photograph all
   * come off `GET /inventory`; this read only decides whether the box header can be drawn. A
   * failure panel would trade a working walk for a message about a panel.
   *
   * ON `reloads` RATHER THAN ON THE SHELF, because a box edit is what changes these rows and
   * `BoxOps` bumps that counter when it makes one. It must: D10 as amended makes Section and
   * Card a VIEW of an index, so a divider edit changes every card decoration in the box as
   * well as the box row — which is why the inventory read is on the same counter and why they
   * are refreshed together rather than separately.
   *
   * `.then(ok).catch(fail)` AND NOT `.then(ok, fail)` — the rule `app/eslint.config.js`
   * enforces. It binds here even though the failure path does nothing: the success handler
   * walks a body off the wire, and the two-argument form would turn a throw in it into an
   * unhandled rejection rather than the silence this effect intends. */
  useEffect(() => {
    let live = true
    getBoxes()
      .then((summary) => {
        if (!live) return
        setBoxRecords(Array.isArray(summary.boxes) ? summary.boxes : [])
      })
      .catch(() => {
        // Deliberately nothing. See above: the walk is whole without this.
      })
    return () => {
      live = false
    }
  }, [reloads])

  /* THE SHELF FOLLOWS THE FILTER, which is the selection rule one level up and it exists for
   * the same failure: a query matching only box 95 while box 1 is selected would draw an empty
   * list under a header naming a box that does have cards, and nothing on screen would say the
   * match was somewhere else. So an unreachable shelf falls to the first one the query does
   * reach. When NOTHING matches, the shelf is deliberately left alone — clearing the query
   * then puts the owner back exactly where they were, and one over-narrow keystroke does not
   * cost them their place. */
  useEffect(() => {
    if (shelves.length === 0) return
    setShelf((prev) =>
      prev !== null && shelves.includes(prev) ? prev : (shelves[0] ?? null),
    )
  }, [shelves])

  /* THE SELECTION FOLLOWS THE FILTER. A query that drops the selected card would otherwise
   * leave the detail panel showing a card the list no longer contains — a photo beside a
   * walk that cannot reach it. First match rather than nothing, because the filtered list
   * is an answer and its first row is the walk's own order speaking. When NOTHING matches,
   * the selection is deliberately left alone: the detail hides on its own (it renders off
   * `visible`), and clearing the query then restores exactly the card that was open —
   * nulling it would make one over-narrow keystroke cost the owner their place. */
  useEffect(() => {
    if (visible.length === 0) return
    setSelected((prev) =>
      prev !== null && visible.some((row) => row.key === prev) ? prev : (visible[0]?.key ?? null),
    )
  }, [visible])

  /* THE ARROW KEYS, armed on the window rather than on the list itself, so the owner does not
   * have to click a row before the keyboard does anything — a fast nav that needs a mouse
   * click to arm it is not one. `trigger.ts` and ReviewQueue.tsx both bind this way and both
   * arm it from an effect that exists only while their screen is mounted; this is that shape
   * a third time, teardown included, which is the half of it that keeps a second mount from
   * leaving two listeners walking the list two cards at a time. The deep keys are the
   * opposite ruling — list-scoped, a React handler on the element itself — and the split
   * is argued at SECTION_KEYS above.
   *
   * `selected` is deliberately NOT a dependency. The move is a functional update, so the
   * handler closes over `visible` alone and is registered once per change of the walk
   * instead of once per keystroke — at auto-repeat pace the second shape churns a window
   * listener thirty times a second, and the stale closure it would otherwise need is a real
   * bug rather than a style question. `visible` and not `rows`, which is how the arrows
   * compose with the search: a held Right walks the MATCHES, in walk order, and never steps
   * onto a card the filter removed.
   */
  useEffect(() => {
    if (visible.length === 0) return

    const onKeyDown = (event: KeyboardEvent) => {
      /* Modifiers belong to the browser and the OS: Cmd-Left is Back and Alt-Left is a word
       * jump, and neither should quietly become a card. Shift is left out of that list for
       * the reason trigger.ts gives — it does not change which key was pressed — and a held
       * Shift silently killing the nav would be the worse of the two failures. */
      if (event.metaKey || event.ctrlKey || event.altKey) return

      const step = STEPS.find((candidate) => candidate.key === event.key)
      if (step === undefined) return
      if (isEditableTarget(event.target)) return

      /* AUTO-REPEAT IS THE FEATURE HERE, which is why there is no `event.repeat` guard and
       * why its absence is written down rather than left looking like an omission. trigger.ts
       * refuses a repeat because a held key there is a stack of captures of one card sitting
       * in the lens; ReviewQueue.tsx refuses one because a held key there is a run of answers,
       * and every answer is a write. Here the action is a selection change on a screen that
       * writes nothing: holding Right walks the box, letting go stops it, and nothing has been
       * spent that has to be walked back.
       *
       * What it does cost is a photo request per card as the panel keeps up. The browser
       * abandons the ones it does not finish, and a debounce was declined: it would leave the
       * photo showing one card while the highlight and the position label showed another,
       * which is precisely the disagreement this screen exists to rule out.
       */

      /* Prevented before the move rather than after it, because a refusal at the end of the
       * list is still this handler answering for the key. The alternative lets a held Right
       * start scrolling the page sideways the moment it runs out of cards, which reads as the
       * list having thrown you somewhere. Every press that reached one of the returns above
       * keeps its normal behaviour, which is the whole reason this line sits here and not at
       * the top. */
      event.preventDefault()

      setSelected((prev) => {
        const at = visible.findIndex((row) => row.key === prev)

        /* Not in this list at all — hard to reach, since the loader plants the selection on
         * the first row and only drops it when there is nothing to select. Step in from the
         * end you are stepping from, so a first press does something rather than nothing. */
        if (at === -1) {
          const landing = step.delta === 1 ? visible[0] : visible[visible.length - 1]
          return landing?.key ?? prev
        }

        /* BOTH ENDS STOP, and the missing index is what stops them: one past either end,
         * `rows[...]` is undefined under noUncheckedIndexedAccess and the selection is left
         * exactly where it was. Wrapping was the alternative and it is the wrong one —
         * arriving back at card 1 after the last card of a two-hundred-card box loses your
         * place without saying so, and the list is then lying about where its end is. A list
         * that stops is telling the truth. */
        return visible[at + step.delta]?.key ?? prev
      })
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [visible])

  /* Keep the selected row where it can be seen. The failure this prevents is specific, and it
   * is the one that makes a keyboard list feel broken: the detail panel updates, the marked
   * row is three screens up inside its own scroller, and the only thing that visibly moved is
   * on the other side of the page.
   *
   * `block: 'nearest'` so it scrolls only when it has to, which is what keeps it from
   * fighting the mouse — a click on a row that was already visible moves nothing. A
   * box-chip jump is the argued exception and lands `block: 'start'`, once, via jumpRef
   * above: a jump is FOR seeing what follows the landing, and 'nearest' shows what
   * precedes it. The rows' scroll-margin in the stylesheet is what keeps 'start' from
   * parking the row under its own sticky section header.
   *
   * READ OFF `aria-current` rather than off a ref per row. That attribute is already this
   * screen's answer to "which row is current", so the row that scrolls is by construction the
   * row that is marked; a parallel map of refs is a second answer to the same question, and
   * the day the two disagree nothing says so. (The box cells carry the attribute too, but
   * they live outside `listRef`, so the query cannot land on one.) `visible` in the
   * dependencies for the handler's own reason: when the filter redraws the list around an
   * unchanged selection, the marked row should still be the one on screen. */
  useEffect(() => {
    const current = listRef.current?.querySelector('[aria-current="true"]')
    if (current instanceof HTMLElement) {
      current.scrollIntoView({ block: jumpRef.current === selected ? 'start' : 'nearest' })
    }
    jumpRef.current = null
  }, [selected, visible])

  /* The deep keys. A React handler on the list rather than a window listener — focus
   * within the list IS the scoping the ruling at SECTION_KEYS asks for, there is nothing
   * to tear down, and a fresh closure per render means no dependency bookkeeping. The
   * guards are the window handler's, in the same order and for the same reasons. */
  const onListKeys = (event: ReactKeyboardEvent<HTMLUListElement>) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return
    if (isEditableTarget(event.target)) return

    const edge = EDGE_KEYS.find((candidate) => candidate.key === event.key)
    const jump = SECTION_KEYS.find((candidate) => candidate.key === event.key)
    if (edge === undefined && jump === undefined) return

    /* Prevented even when the move refuses, exactly as the arrows argue: a refusal at the
     * end is still this handler answering for the key, and the default here — the scroller
     * paging the ROWS out from under an unmoved selection — is precisely the disagreement
     * between the mark and the viewport this screen exists to rule out. */
    event.preventDefault()

    if (edge !== undefined) {
      const landing = edge.last ? visible[visible.length - 1] : visible[0]
      if (landing !== undefined) setSelected(landing.key)
      return
    }
    if (jump === undefined) return

    setSelected((prev) => {
      const at = sections.findIndex((section) => section.rows.some((row) => row.key === prev))

      /* Not in any section — the same hard-to-reach case the arrows handle, answered the
       * same way: step in from the end being stepped from. */
      if (at === -1) return sections[0]?.first.key ?? prev

      if (jump.delta === 1) return sections[at + 1]?.first.key ?? prev

      /* Backwards: the nearest boundary first — this section's own start from its middle,
       * the previous section's from its start. Both ends stop, by the arrows' own
       * mechanism: one past either end is undefined under noUncheckedIndexedAccess and the
       * selection stays put. */
      const own = sections[at]
      if (own !== undefined && own.first.key !== prev) return own.first.key
      return sections[at - 1]?.first.key ?? prev
    })
  }

  /* A CELL PRESS CHANGES WHAT THE WALK IS OF, and then does the two things a click on a row
   * does not. It scrolls the landing to the top of the scroller — via jumpRef, argued at the
   * scroll effect — and it hands focus to the list, arming the deep keys: the gesture after
   * "show me box 7" is walking box 7, and a selection that left the keys dead until a click
   * would give back the mouse it just saved.
   *
   * The landing is computed off `inQuery` rather than `visible` for a reason that is easy to
   * get wrong: `visible` is the shelf you are LEAVING at the moment this runs, so it holds no
   * row of the shelf being asked for. `inQuery` is every row the current query reaches, on any
   * shelf, which is where the landing has to come from. */
  const selectShelf = (next: Shelf) => {
    setShelf(next)
    const landing = inQuery.find((row) => shelfOf(row) === next)
    if (landing !== undefined) {
      jumpRef.current = landing.key
      setSelected(landing.key)
    }
    listRef.current?.focus()
  }

  /* Off `visible`, not off `rows`: a selection the filter removed renders NO detail rather
   * than a card the list cannot reach — and comes back whole when the query clears. */
  const selectedRow = visible.find((row) => row.key === selected) ?? null

  /* Read once for the selected card and passed down, rather than read again inside
   * PhotoPanel. Two reads of the same field cannot disagree today, but they are two places
   * to edit the day the field is renamed, and the failure mode of getting that half-right
   * is a photo captioned with a position beside a panel saying there is none. */
  const selectedLabel = selectedRow === null ? null : positionLabel(selectedRow.card)

  /* Read once beside the label it sits under, for the label's own reason: one read, one
   * value, and no way for the sentence's presence test and its rendering to disagree. */
  const selectedSentence = selectedRow === null ? null : placeSentence(selectedRow.card.place)

  return (
    <section className="browse">
      {/* NO <h1> AND NO LEDE HERE ANY MORE. This is a mode of `#/inventory`, not a page, and
          that screen's header carries the title, the sentence and the two-way switch. A second
          heading under the first would put two titles on one screen — and the one this file
          used to draw named a route that no longer exists. */}
      <div className="browse-head">
        <div className="browse-controls">
          {/* A reload is a GET. The ban in §7 is on acting — writing a state, marking a
              sale, pulling a card — and re-reading the inventory is none of those. It
              earns its place because Gate B alternates between capturing on one screen and
              checking here, and the alternative is teaching the operator to reload the
              browser, which also throws away the selection. No accent fill: docs/DESIGN.md
              reserves the solid fill for a screen with exactly one thing to do, and this
              screen's one thing is to be looked at. */}
          <button className="browse-reload" type="button" onClick={() => setReloads((n) => n + 1)}>
            Reload
          </button>
          {rows === null ? null : (
            <span className="browse-count">
              {rows.length} {rows.length === 1 ? 'card' : 'cards'}
            </span>
          )}
          {/* "Every choice shows its key" — docs/DESIGN.md, owner-side, where an hour spent
              checking a run against the boxes on the desk is a keyboard and not a mouse. A
              hotkey nobody can see is a hotkey nobody uses, and this screen had no chrome to
              discover it from at all.

              In the header rather than pinned to the list, because that is where the binding
              actually is: the keys are on the window and work wherever you are on this screen,
              so a chip attached to the list would claim a smaller thing than the truth. The
              deep keys are the same rule pointing the other way — bound on the list, so their
              chips sit under it.

              Drawn only with two cards to step between. A hint offering to move you through a
              list of one is chrome that has stopped being true, and the empty and failed
              states have no list under it at all. */}
          {rows === null || rows.length < 2 ? null : (
            <span className="browse-keys">
              {STEPS.map((step) => (
                <kbd className="browse-key" key={step.key}>
                  {step.label}
                </kbd>
              ))}
              step one card
            </span>
          )}
        </div>
      </div>

      {failure === null ? null : (
        <div className="browse-note">
          <p className="browse-note-text">{failure.message}</p>
          {/* The CODE beneath the sentence, and never the sentence again.
              docs/DESIGN.md's rule is "human label large, machine string small beneath
              it", and the machine string it means is a greppable token — `store_busy`,
              `unreachable` — that says something the label above it does not. An earlier
              draft printed the server's one message in both slots, which is not that rule
              but a stutter, and it cost the small line the only job it has: getting from
              what is on screen to what the server said, with `git grep`. Owner-side only,
              and this screen is owner-side. */}
          <p className="browse-machine">{failure.code}</p>
        </div>
      )}

      {rows === null && failure === null ? (
        <p className="browse-note-text">Reading the inventory.</p>
      ) : null}

      {rows !== null && rows.length === 0 ? (
        <p className="browse-note-text">No cards captured yet.</p>
      ) : null}

      {rows !== null && rows.length > 0 ? (
        <div className="browse-body">
          {/* The map column: search, box strip, status line, the list, then the keys that
              walk it. One column because they are one instrument — everything in it narrows
              or indexes the same walk, and the detail panel beside it is what the walk is
              pointing at. */}
          <div className="browse-map">
            {/* The shared field: owner persona, `/` from anywhere, Esc handing focus back
                with the query intact — all SearchField's own rulings, not re-made here. The
                search-shape argument and the deliberate absence of autoFocus are at the
                useSearch call above. */}
            <SearchField value={query} onChange={setQuery} persona="owner" />

            {/* THE BOX STRIP — the capture screen's segmented-track idiom, not a row of
                buttons and not a <select>. Thirty boxes must fit over a 240-320px column,
                which rules out thirty padded chips by arithmetic; a native select fits any
                count by hiding the map behind a click, and a map you have to open is not a
                map. Hairline-divided 10px utility cells wrap to a second row past roughly a
                dozen boxes, which costs 20px and hides nothing.

                IT SELECTS RATHER THAN JUMPS NOW (D31) — the header at the top of this file
                argues the change. `aria-current` still marks where you are, so the strip still
                doubles as "you are here"; what moved is that the rail follows the SHELF rather
                than the selected card's box, and those were the same fact only while one walk
                held every box.

                DRAWN EVEN WITH ONE SHELF, which reverses the old rule and does not contradict
                it. A strip of one chip that jumps you to a row you can already see is chrome;
                a strip of one cell that NAMES the box the list below is of is the only place
                that fact appears when the box registry has not answered. */}
            {shelves.length === 0 ? null : (
              <div className="browse-boxline">
                <span className="browse-boxcap" aria-hidden="true">
                  Box
                </span>
                <div className="browse-boxes" role="group" aria-label="Choose a box to walk">
                  {shelves.map((cell) => (
                    <button
                      key={String(cell)}
                      className="browse-boxcell"
                      type="button"
                      aria-label={
                        cell === 'pooled'
                          ? 'Pooled cards, which have no box'
                          : cell === 'unplaced'
                            ? 'Records with no readable box'
                            : `Box ${cell}`
                      }
                      aria-current={cell === shelf ? 'true' : undefined}
                      onClick={() => selectShelf(cell)}
                    >
                      {shelfLabel(cell)}
                    </button>
                  ))}
                </div>
              </div>
            )}


            {/* The search's own failure, in the owner idiom: the sentence, then the
                greppable code. The walk below it is deliberately UNFILTERED while this
                stands — see the `visible` memo. */}
            {searchFailure === null ? null : (
              <div className="browse-note browse-mapnote">
                <p className="browse-note-text">{searchFailure.message}</p>
                <p className="browse-machine">{searchFailure.code}</p>
              </div>
            )}

            {/* `loading` is true through the debounce as well as the request — useSearch
                says why — so this line is the honest answer to "is the list below an answer
                to the box above", drawn beside the old list rather than instead of it. */}
            {searching && loading ? <p className="browse-match">Looking.</p> : null}
            {searching && !loading && results !== null ? (
              <p className="browse-match">
                {inQuery.length === 0
                  ? `Nothing in the boxes matches ${results.query}.`
                  : `${visible.length} on this box · ${inQuery.length} of ${rows.length} ${
                      inQuery.length === 1 ? 'card matches' : 'cards match'
                    }`}
              </p>
            ) : null}

            {/* Focusable and labelled, so the interaction is reachable rather than
                folklore: a keyboard user gets a tab stop that announces itself as the list
                of cards and says which keys it answers to. `aria-keyshortcuts` is the
                machine-readable half of the chips — the same facts, said once to a person
                and once to a screen reader. The arrows are bound on the window and deliver
                MORE than the attribute claims; the deep keys are bound on this element and
                deliver exactly. Neither direction over-claims, which is the safe way for
                the attribute to be imprecise. */}
            {visible.length === 0 ? null : (
              <ul
                className="browse-list"
                ref={listRef}
                tabIndex={0}
                aria-label="Captured cards, in box-walk order"
                aria-keyshortcuts="ArrowLeft ArrowRight PageUp PageDown Home End"
                onKeyDown={onListKeys}
              >
                {sections.map((section) => (
                  /* One li per stretch of the walk, its header sticky WITHIN it: the header
                     holds the scroller's top edge while its own rows pass and is pushed off
                     by the next one — so "where am I" is always on screen, which is the
                     first thing a two-hundred-row scroller loses. */
                  <li className="browse-group" key={section.key}>
                    <div className="browse-secthead">{section.title}</div>
                    <ul className="browse-group-rows">
                      {section.rows.map((row) => (
                        <li key={row.key}>
                          {/* Plain buttons, and they stay plain buttons now that the arrow
                              keys are bound. Tab reaches every one of them for free, the
                              click path is untouched, and `aria-current` below is still the
                              one mark of which row is current — a roving-focus listbox
                              would trade all three for an activedescendant dance this
                              screen does not need.

                              FOCUS DELIBERATELY DOES NOT FOLLOW THE SELECTION. It is the
                              obvious next step and it is the wrong one: a held Right would
                              fire a focus move per card, dragging focus out of wherever the
                              owner left it and scrolling on its own account, thirty times a
                              second. The row is marked, not focused, and the scroll effect
                              above is what keeps it on screen.

                              The sentence this replaces said a key map here would be "a
                              vocabulary to learn for no decision". That was true of a
                              screen driven with a mouse and stopped being true the moment
                              the owner asked to walk a box from the keyboard — two keys,
                              one meaning, and still nothing written.

                              One line per card now — the slot under its section header,
                              then the name. rowSlot above says what the left cell is
                              allowed to claim, fallbacks included. */}
                          <button
                            className="browse-row"
                            type="button"
                            aria-current={row.key === selected ? 'true' : undefined}
                            onClick={() => setSelected(row.key)}
                          >
                            <span className="browse-row-position">{rowSlot(row)}</span>
                            <span className="browse-row-name">
                              {row.card.name ?? row.card.state}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            )}

            {/* The deep keys' chips, ON the list rather than in the header — the ruling at
                SECTION_KEYS: the header advertises window keys, this advertises list keys,
                and each chip sits where its binding lives. The condition is said out loud
                because it is the one fact about these keys nobody can guess from the
                chrome. */}
            {visible.length < 2 ? null : (
              <p className="browse-keys browse-listkeys">
                {SECTION_KEYS.map((step) => (
                  <kbd className="browse-key" key={step.key}>
                    {step.label}
                  </kbd>
                ))}
                a section
                {' · '}
                {EDGE_KEYS.map((step) => (
                  <kbd className="browse-key" key={step.key}>
                    {step.label}
                  </kbd>
                ))}
                the ends · when the list holds focus
              </p>
            )}

            {/* Register a box before a card goes into it — D20's control, in the column that
                lists every box it would join, at the bottom of it.

                UNDER THE WALK RATHER THAN OVER IT, and the reason is measured. This column is
                sticky and its height is the viewport, so everything above the list is height
                the list does not get: drawn between the strip and the walk this control cost
                44px of rows, permanently, to offer an action taken a handful of times a year.
                Below, it costs nothing until the list is short enough to leave room. It is
                still beside the strip in the sense D20's own argument needs — every existing
                box is listed in the same column, which is what makes a mistyped number
                visible. */}
            <RegisterBox onChanged={() => setReloads((n) => n + 1)} />
          </div>

          <div className="browse-side">
            {/* THE BOX HEADER — D31's "box operations live on the box header inside the
                browse, beside the box they operate on". It is the first thing in the detail
                column rather than a strip across the top of the walk, and that is a measured
                choice: `#/boxes` drew this panel for every box at once and cost 1744px of
                scroll to say four things, so the panel is drawn once, for the box being
                walked, with its layout table and its four controls folded (see BoxOps).

                DRAWN ONLY FOR A NUMBERED SHELF THE REGISTRY KNOWS. The pooled and no-box
                shelves are not boxes and have nothing to rename or seal; a box a card names
                that `GET /boxes` has not answered for gets no panel rather than an invented
                one. `onChanged` bumps the same counter the Reload does, which re-reads the
                registry AND the inventory — a divider edit relabels every card in the box
                (D10 as amended), so the walk has to be re-read with the panel. */}
            {shelfBox === null ? null : (
              <BoxOps record={shelfBox} onChanged={() => setReloads((n) => n + 1)} />
            )}

            {shelf === 'pooled' ? (
              <div className="browse-gap">
                <p className="browse-note-text">
                  These cards are pooled — a count, not a location (D24). They have no box,
                  section or card position, so there is no box to name, divide or seal.
                </p>
                <p className="browse-machine">located: false</p>
              </div>
            ) : null}

            {shelf === 'unplaced' ? (
              <div className="browse-gap">
                <p className="browse-note-text">
                  These records reached the store with a box or an index that is not a number,
                  so the capture server sent them with no position at all. `GET /status`
                  reports them; nothing here can name a box for them.
                </p>
                <p className="browse-machine">place: absent</p>
              </div>
            ) : null}

          {selectedRow === null ? null : (
            <section className="browse-detail">
              {selectedLabel === null && isPooled(selectedRow.card) ? (
                /* Pooled, not missing — the deliberate case, before the fault below can
                   claim it. The sentence says what the card IS so the absent label stops
                   looking like something to go and fix. */
                <div className="browse-gap">
                  <p className="browse-note-text">
                    This card is pooled — a count, not a location. It has no box, section or
                    card position to show; the key below names its photo and sidecar on
                    disk, and nothing else.
                  </p>
                  <p className="browse-machine">
                    located: false · {pooledText(selectedRow.card, selectedRow.key)}
                  </p>
                </div>
              ) : selectedLabel === null ? (
                /* The gap, drawn as a panel in the space the label would have filled.
                   Loud rather than blank: this screen's whole claim is that it says where
                   a card is, and a screen that has quietly stopped making that claim
                   should not look like one that is still making it. */
                <div className="browse-gap">
                  {/* Both causes, because the sentence has to survive being read on the
                      wrong one: a restart fixes an old server and does nothing at all for a
                      record whose box will not coerce. Naming only the likelier one would
                      send the operator round a loop that cannot work. */}
                  <p className="browse-note-text">
                    The capture server sent no position label for this card, and this screen
                    does not work one out for itself. Either an older server is running —
                    restart it with `make server` and reload — or this record's box or index
                    is not a number, which `GET /status` reports.
                  </p>
                  {/* The field and its state, in the shape the missing-photo panel below
                      uses — `photo: null` there, `label: absent` here — plus the store key,
                      which is what a `curl /inventory | grep` needs to see it for itself. */}
                  <p className="browse-machine">label: absent · key {selectedRow.key}</p>
                </div>
              ) : (
                /* The payload of the whole screen. Utility face because it is a position,
                   and sized up because it is the one thing being checked against a physical
                   box across the desk. */
                <>
                  <p className="browse-position">{selectedLabel}</p>
                  {/* D30's sentence, quiet, directly under the label it makes countable:
                      "between Mantine and Thievul · 2 slots in this section are empty".
                      `Card 17` is the seventeenth SLOT, and once the section has permanent
                      gaps that is no longer the seventeenth card a hand can count to —
                      the neighbours restore the count and the gap tally says why it came
                      out short. Composed by `server.ts:placeSentence`, the one composer,
                      which answers null — and this renders nothing, never a guess — for a
                      pooled card, an older server, or a decoration the server degraded. */}
                  {selectedSentence === null ? null : (
                    <p className="browse-between">{selectedSentence}</p>
                  )}
                </>
              )}

              <PhotoPanel
                row={selectedRow}
                label={selectedLabel}
                absent={photoAbsent === selectedRow.key}
                onAbsent={() => setPhotoAbsent(selectedRow.key)}
                nonce={reshot[selectedRow.key] ?? null}
              />

              <ReshootControl
                row={selectedRow}
                busy={reshootBusy === selectedRow.key}
                failure={
                  reshootFailure !== null && reshootFailure.key === selectedRow.key
                    ? reshootFailure.failure
                    : null
                }
                onPick={(file) => beginReshoot(selectedRow, file)}
              />

              <dl className="browse-facts">
                {detailsOf(selectedRow.card).map((detail) => (
                  <div className="browse-fact" key={detail.label}>
                    <dt>{detail.label}</dt>
                    <dd className={detail.mono ? 'is-util' : undefined}>{detail.value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}
          </div>
        </div>
      ) : null}
    </section>
  )
}

type PhotoPanelProps = {
  row: Row

  /** The server's own position label, or null when this row arrived without one. Handed
   *  down rather than derived here — see the note beside `selectedLabel`. */
  label: string | null

  absent: boolean
  onAbsent: () => void

  /** The capture id of a photo THIS SESSION replaced at this position, or null for the
   *  ordinary card. Non-null appends `?reshot=<id>` to the img src — see the comment at
   *  `base` below for why that is the one legitimate query parameter on this URL. */
  nonce: string | null
}

/* Two ways a photo can be missing, and they are different facts, so they get different
 * sentences rather than one broken image.
 *
 *   `photo` is null   — no photo was ever stored. `emit` can record a card that was never
 *                       photographed, and `store/master.py` keeps the field null for it.
 *   the route 404s    — the record claims a photo and the file is not there. That is a
 *                       store that has lost something, and it is worth saying so plainly.
 *
 * Both print the URL that was asked for, so the next move is a curl rather than a guess.
 */
function PhotoPanel({ row, label, absent, onAbsent, nonce }: PhotoPanelProps) {
  /* One phrasing, used by both the sentence beside a missing photo and the alt text on a
   * present one, so those two cannot end up disagreeing about where the card is. The
   * fallback says `store key` out loud rather than printing `3/30` bare: bare, it reads
   * like a position, and the whole point of the null case is that no position was sent. */
  const where = label ?? `store key ${row.key}`

  if (row.card.photo === null) {
    return (
      <div className="browse-absent">
        <p className="browse-note-text">No photo was stored for this card.</p>
        <p className="browse-machine">photo: null</p>
      </div>
    )
  }

  /* The URL as `server.ts` mints it — with nothing appended, EXCEPT after a re-shoot.
   *
   * There is a real hazard here and it is worth naming rather than inheriting silently:
   * undo deletes a photo and releases its index, so the next capture reuses this exact URL
   * for different bytes, and `GET /photo` sends no `Cache-Control`, no `ETag` and no
   * `Last-Modified`. A browser that held one of these would show a stale photo at a correct
   * position — precisely the failure this screen exists to catch, and invisible when it
   * happens.
   *
   * A LOAD-TIME cache-busting parameter minted here was written and then removed, and it
   * stays removed. `server.ts:photoUrl`'s comment rejects that fix by name — the general
   * repair belongs in a response header on the server, one line in
   * `server/capture_server.py:_send` — and a nonce on every render would defeat what
   * caching this screen benefits from while papering over the missing header.
   *
   * THE RE-SHOOT NONCE IS THE ONE EXCEPTION, ARGUED AGAINST THAT COMMENT RATHER THAN
   * AROUND IT. What that comment refuses is a guess: a parameter added on every load
   * because the bytes MIGHT have changed. After `reshootPhoto` succeeds there is no might
   * — THIS screen sent the new bytes to this exact URL, so rendering the src that a
   * moment ago showed the photograph it just destroyed is showing a picture the store no
   * longer holds, the stale-photo failure above realised by our own hand. One screen, at
   * the one moment it knows, appending the id of the photograph it expects: that is
   * cache-busting as a statement of fact, not as a workaround, and photoUrl's comment now
   * names it as the standing exception. */
  const base = photoUrl(row.card.box, row.card.index)
  const src = nonce === null ? base : `${base}?reshot=${nonce}`

  if (absent) {
    return (
      <div className="browse-absent">
        <p className="browse-note-text">
          The record has a photo but the file is not on disk. The card is still at {where} —
          and a photo added below replaces nothing, it is the first one this position would
          have again.
        </p>
        <p className="browse-machine">{src}</p>
      </div>
    )
  }

  return (
    <img
      /* Remounted per card AND per replacement: `src` in the key means a re-shoot swaps
         the element rather than mutating it, so a failed load cannot leave the previous
         photograph's broken state attached to the new one. */
      key={`${row.key}:${src}`}
      className="browse-photo"
      src={src}
      alt={`The card photographed at ${where}`}
      onError={onAbsent}
    />
  )
}

/* The re-shoot control — the pull preview's one write. The header at the top of this file
 * carries the ruling (D26's second half, placed here by the owner) and the no-dialog
 * argument; what this component decides is the MECHANISM, and the honest one on this
 * screen is a file.
 *
 * NOT A CAMERA, ON PURPOSE. This screen has none, and wiring one in would duplicate the
 * capture screen's whole device-picker apparatus (D13: no facingMode, UVC labels, a
 * rotation chip) for a control used once in a while. The rig capture screen is for live
 * shooting; this control replaces a bad STORED photo with a better frame from wherever
 * the owner has one — a re-shot rig frame saved to disk, a phone photo airdropped over.
 * `accept="image/jpeg"` because the server stores what it is given and never converts
 * (`image_not_jpeg` is its word on anything else, rendered verbatim below).
 *
 * NOT DRAWN AT ALL FOR A SOLD OR RETIRED CARD — the `restores_to` lesson, learned twice:
 * never offer a control whose only behaviour is a refusal. The server would refuse both
 * (`card_sold`: the stored photo is the dispute record; `card_retired`: a photo of a card
 * that left is a photo of nothing), and this screen reads the same state field the server
 * checks. Not-rendered rather than disabled, the same ruling the shell applies to nav.
 */
type ReshootControlProps = {
  row: Row
  busy: boolean

  /** This card's own refusal or null — the caller keys failures by row so another card's
   *  refusal cannot render under this card's photo. */
  failure: Failure | null

  onPick: (file: File) => void
}

function ReshootControl({ row, busy, failure, onPick }: ReshootControlProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)

  if (row.card.state === 'sold' || row.card.state === 'retired') return null

  return (
    <div className="browse-reshoot">
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0]
          /* Cleared before use, so picking the SAME file again fires onChange again —
           * which is exactly what a retry after a refusal is. */
          event.target.value = ''
          if (file !== undefined) onPick(file)
        }}
      />
      {/* No accent fill: docs/DESIGN.md reserves the solid fill for a screen with exactly
          one thing to do, and this screen's one thing is still to be looked at. The label
          changes with the fact — a card `emit` recorded without a photograph has nothing
          to re-shoot, and the route's own comment calls that case the first photograph
          the position has, so the button says so rather than claiming a replacement. */}
      <button
        className="browse-reload"
        type="button"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
      >
        {busy
          ? 'Replacing the photo…'
          : row.card.photo === null
            ? 'Add a photo'
            : 'Re-shoot this photo'}
      </button>
      {failure === null ? null : (
        <div className="browse-note">
          <p className="browse-note-text">{failure.message}</p>
          <p className="browse-machine">{failure.code}</p>
        </div>
      )}
    </div>
  )
}
