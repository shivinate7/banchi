import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'

import type { CardSummary, FinishClaim, GameEntry, GameRegistry } from './types'
import {
  ServerError,
  capture,
  getGames,
  getStatus,
  newCaptureId,
  photoUrl,
  undoCapture,
  updateCard,
} from './server'
import { manualTrigger } from './trigger'
import { motionTrigger } from './motion'
import type { MotionDiagnostics } from './motion'
import { MotionTrace } from './trace'
import { DEFAULT_PARAMS } from './motion'
import { useCamera, PIPELINE_LONG_EDGE, ROTATIONS } from './useCamera'
import { PullConfirm } from './PullConfirm'
import './CaptureScreen.css'

/* The capture screen — docs/specs/capture-app.md section 5.
 *
 * The screen the owner spends hours in, and the only one Gate B exercises end to end. Every
 * shape below is settled in that spec against a named alternative; where this file makes a
 * call the spec left open, the comment says so and names what it beat.
 *
 * The one thing to hold on to while reading: a card that passes the lens with no record and
 * no photo is unrecoverable — nothing afterwards can say which card it was. Section 5.5 is
 * the whole reason a failed capture stops the run instead of retrying quietly, and the
 * in-flight guard, the halt state and the disabled control below all serve that one rule.
 */

// The trigger seam (spec section 6). Gate B fired on this key and button; the motion
// machine (Gate C, src/motion.ts) sits in the same slot behind the mode toggle below.
//
// 'c' rather than Space or Enter, which are the obvious rig keys and lost for a specific
// reason: both activate whatever button currently has focus. Click Undo with the mouse and
// Space would then mean undo AND capture on every press — a double-fire that writes a
// position for a card nobody photographed. A letter key activates nothing.
const CAPTURE_KEY = 'c'
const UNDO_KEY = 'u'

// What the chips say. The key compared against `event.key` is lower case; the chip is not.
const CAPTURE_KEY_LABEL = 'C'
const UNDO_KEY_LABEL = 'U'

// Finish strings are rendered VERBATIM rather than as friendly labels: D3 rung 1 treats the
// claim as trusted, and the string on screen is the string written into the sidecar and
// quoted back by a review reason. Friendly labels would create a second vocabulary nothing
// audits — docs/DESIGN.md's own argument for showing reason codes as well as names.
//
// The list itself used to live here as `FINISHES`, Pokemon's three. It is per-game data now
// and comes from `GET /games`; see `finishChips` below.

/* THE DEFAULT STATE OF THE FINISH CONTROL — no claim at all — and, since 2026-08-23, a
 * LABEL RATHER THAN A CELL.
 *
 * It used to be drawn as the track's first cell, which made "claim nothing" a thing to pick
 * beside the things there are to claim. The owner's ruling: nothing selected already IS no
 * claim, so the cell only restated the absence of the others. It went; this label stayed,
 * because the state still has to be NAMED wherever it is read — the collapsed Row and the
 * last-capture panel both still say it at full contrast. Clearing a claim is re-tapping the
 * cell that is on, which is what the rarity claim beside it already did and what `Track`'s
 * `aria-pressed` markup always described.
 *
 * It is not a member of any game's enum — the server answers anything outside THE CHOSEN
 * GAME's finishes with `variant_invalid` (`_check_variant_members`; it was Pokemon's three
 * under every game until the day this comment was rewritten, which is the bug that cost a
 * Riftbound `foil` its capture) — it is `null`, and it sends no `variant` key at all,
 * exactly as a blank set hint sends no `set_hint`. Both rules come from the same sentence
 * in `sidecar_payload`: the file stays a record of claims the operator actually made
 * (D3 rung 1).
 *
 * THE NEXT PERSON TO TIDY THIS WILL WANT TO DEFAULT IT TO 'normal'. What that costs is
 * structural rather than cosmetic. `pipeline/variant.py:resolve` reaches rung 2
 * (CATALOG_FORCED, "one condition row for that number, so the row decides") and rung 3
 * (detection as a cross-check) only where the sidecar recorded no variant. A default claim
 * on every capture makes both rungs unreachable for every card this product will ever
 * photograph — and D3's own example, the holofoil-only SV-era rare, then returns
 * METADATA_NOT_STOCKED and costs a review-queue tap in place of resolving untouched. That
 * is the zero-attention-per-card property in CLAUDE.md's first line, spent on a claim
 * nobody made.
 *
 * Lower case with a space, which no member of the enum can be. Same trick as the undo
 * fallback further down: a state label must never be readable as a machine string.
 */
const NO_CLAIM_LABEL = 'no claim'

/* `identify/prompt.py:UNWRITTEN` — the one registry strategy name this screen compares
 * against, and the only string here that duplicates a Python literal.
 *
 * It is not a mirror of the vocabulary and must not grow into one: `PROMPT_STRATEGIES` has
 * three members and the app cares about exactly one of them, because "this game has no
 * prompt YET" is a fact the operator can act on — it means a card captured now will need
 * re-identifying later. The other two are the app's business only through fields it already
 * gets: `catalogued` says a game is never identified at all, and `unverified` says it cannot
 * be captured. A `games.ts` holding all three would be the second copy `types.ts` argues
 * against, for one comparison.
 *
 * If the registry ever renames it, this comparison quietly stops matching and the chip loses
 * its second line — a missing hint, never a wrong capture. That is the failure this is worth
 * accepting; anything that decided a CLAIM off a duplicated literal would not be.
 */
const PROMPT_UNWRITTEN = 'unwritten'

/** One capture made in this session: what the server recorded, and what we sent with it. */
type Shot = {
  card: CardSummary
  // The client's own copy of what accompanied this photo, NOT a server echo — the capture
  // response carries neither. Shown under the photo because the bar above shows what the
  // *next* card will get, and a stack toggled wrong is D3's expensive failure: it is
  // discovered here or not until the review queue.
  setHint: string | null
  // EMPTY when nothing was claimed, which is what was sent: no `variant` key at all. Shown
  // as such rather than as 'normal', because the whole point of the state is that the two
  // are different things. A SET since D3 rung 1's amendment of 2026-08-23, so this is what
  // the stack was said to hold rather than what one card was said to be.
  finish: FinishClaim
  // NOT NULLABLE, unlike the two above, and that is D21 rather than an oversight: a game is
  // always claimed, so there is always one to record here. Kept per shot for the same
  // reason as the other two — the sidebar shows what the NEXT card gets, and the game is
  // the one claim that decides whether this card will ever be identified at all.
  game: GameEntry
}

/** A message the app shows verbatim. `code` is the server's own error code, or null when
 *  the failure never reached the server. */
type Note = { text: string; code: string | null }

/** A stopped run. `where` decides what to do next, which is the only thing the app adds to
 *  the server's own message — spec section 4 forbids paraphrasing that message. */
type Halt = Note & { where: 'camera' | 'server' }

/** What the next undo would delete. `label` is null for a card captured before this session
 *  loaded: `pipeline/join.py:Position.label` renders that string and the app never composes
 *  a second one, so with no capture response in hand there is nothing to show but the two
 *  numbers the server gave us. */
type UndoTarget = { box: number; index: number; label: string | null }

/** What to call a position on screen — the server's own rendered label, or the two raw
 *  numbers when there is no capture response holding one.
 *
 *  Lower case and no separators in the fallback, so it can never be mistaken for the
 *  rendered label: `Box 3 · Section 1 · Card 7` is a string only `pipeline/join.py` writes,
 *  and a client-side imitation of it would be a second copy of D10's divider size that
 *  nothing keeps in step. Both forms go on screen in the utility face — a position is
 *  metadata, and docs/DESIGN.md gives every number in the product to Martian Mono. */
function positionText(target: UndoTarget): string {
  return target.label ?? `box ${target.box}, index ${target.index}`
}

/* What counts as a box on the way in: digits, and nothing else.
 *
 * Deliberately not `Number.parseInt`, which was here and reads '1e3' as 1 and '3.7' as 3 —
 * handing back a DIFFERENT box that is entirely valid and that the operator never typed.
 * Neither is hypothetical: `<input type="number">` accepts both as values, so both arrive
 * here as strings, and the box decides which physical box a photo is filed into. A wrong
 * one is a real photo at a real position in a box that was never opened, which is the same
 * class of damage as the 33-for-3 typo spec 5.2 accepted knowingly — accepted there because
 * the operator typed it, and not acceptable here because nobody did.
 *
 * Leading zeros are allowed through ('003' is 3): they are unambiguous and a rig operator
 * typing one meant the box they got.
 */
const BOX_DIGITS = /^[0-9]+$/

/* ---- what survives a reload, and nothing else does (D27) ----
 *
 * CLAUDE.md bans browser storage and that ban is about INVENTORY. D13 puts one truth on the
 * Mac so the owner's device and the Fulfiller's cannot disagree about where a card is, and
 * `docs/specs/capture-app.md` section 9's "no second store in the browser" is about captures,
 * which still go straight to the server. None of that was ever about the capture screen's own
 * scratch state, and reading it that way cost a real thing: everything below was `useState`,
 * so a reload in the middle of a run threw away the box, the set hint, the finish claim, the
 * game — and the in-flight capture id, which is the one that matters.
 *
 * THE CAPTURE ID IS WHY THIS EXISTS. It is the replay guard: when a capture's response is
 * lost, resending the same id lets the server answer with the position it already committed
 * instead of burning a second one. Held in a ref it did not survive a reload, and a reload
 * during a halt therefore made that ambiguity PERMANENTLY unresolvable — one physical card
 * with two positions or none, and D10's high-water mark handing the burned index to the next
 * card off the feeder. Nothing else on this screen has a failure of that shape.
 *
 * `sessionStorage`, NEVER `localStorage`, and the difference is the point. A shift ends when
 * the tab closes; a new tab is a new shift. That is exactly right for a claim about the stack
 * currently in front of the lens, and it is what makes the held capture id safe to keep:
 * closing the browser is what clears an id nobody is coming back to resolve. `useCamera.ts`
 * uses `localStorage` for the device id and the rotation, and those are the precedent rather
 * than the subject — they are facts about THIS MACHINE, wrong on any other, and a remembered
 * camera cannot take a photograph on its own. `app/eslint.config.js` holds the boundary open
 * in exactly one file for exactly that reason.
 *
 * THE KEYS ARE NAMED HERE AND NOWHERE ELSE, so the boundary is checkable rather than
 * remembered. Nothing about a card, a position or the inventory is in this list and nothing
 * about one may be added to it: what is stored is the claims the operator has set and the id
 * of the photograph in flight.
 *
 * TRIGGER MODE IS DELIBERATELY ABSENT. D19 keeps arming an act rather than a setting, and a
 * motion machine that came back armed after a reload is an automatic shutter pointed at
 * whatever is in front of the lens, with nobody having asked for it this session. Every
 * session starts manual. The same goes for the halt: it is the screen's reaction to one
 * request failing, not a claim, and the server's own message — which section 4 forbids
 * paraphrasing — is not ours to reconstruct from a store an hour later.
 *
 * The `pkmnscan.session.` prefix rather than `useCamera`'s `pkmnscan.capture.` is so that a
 * key read out of devtools says which store it belongs to. Two stores with one prefix is a
 * boundary you have to remember, which is the thing this block exists to stop.
 */
const SESSION_KEYS = {
  box: 'pkmnscan.session.box',
  setHint: 'pkmnscan.session.setHint',
  finish: 'pkmnscan.session.finish',
  game: 'pkmnscan.session.game',
  // D23's stack claim, as JSON — the one non-scalar in this store, because the claim is a
  // LIST of the game's exact Rarity cells and flattening it to a joined string would be a
  // second spelling of a vocabulary D22 says renders verbatim. Same clock as the rest: a
  // claim about the stack at the lens, dead when the tab closes.
  rarityClaim: 'pkmnscan.session.rarityClaim',
  captureId: 'pkmnscan.session.captureId',
} as const

/* Storage can throw outright — Safari private browsing, a profile with site data disabled,
 * and `setItem` can throw on quota as well. `useCamera.ts` records the rule and it applies
 * here with more force: losing a remembered camera costs one click, and letting the exception
 * out white-screens the view the owner spends hours in. A screen that will not render is a
 * strictly worse outcome than a screen that has forgotten which box you were in.
 *
 * Empty string reads back as null on purpose: it is the shape a cleared text field would
 * write, and "the operator typed nothing" is the same state as "nothing was stored". */
function readSession(key: string): string | null {
  try {
    const stored = window.sessionStorage.getItem(key)
    return stored === null || stored === '' ? null : stored
  } catch {
    return null
  }
}

function writeSession(key: string, value: string | null): void {
  try {
    if (value === null) window.sessionStorage.removeItem(key)
    else window.sessionStorage.setItem(key, value)
  } catch {
    /* Ignored on purpose. See readSession. */
  }
}

/* A STORED VALUE IS INPUT, NOT STATE. It can be hand-edited in devtools, and it can be stale
 * in ways the live control could never produce — a box that was legal when it was typed, a
 * finish claim from before the game was changed. Each reader below is the same shape as the
 * control's own validation rather than a weaker version of it, because a value that skips the
 * control's check is a value the control could not have produced.
 */

/** Digits, a safe integer, 1 or higher — `onBoxSubmit`'s rule exactly, and it has to be: the
 *  box decides which physical drawer a photograph is filed into. `'1e3'` and `'3.7'` are both
 *  things `Number` will read as a different, entirely valid box that nobody typed. */
function readSessionBox(): number | null {
  const stored = readSession(SESSION_KEYS.box)
  if (stored === null || !BOX_DIGITS.test(stored)) return null
  const value = Number(stored)
  return Number.isSafeInteger(value) && value >= 1 ? value : null
}

/** Free text, and there is nothing here to validate beyond its being a string — which
 *  `getItem` already guarantees. Recorded as a decision rather than left as a gap: a length
 *  cap or a set-code pattern would make a restored hint stricter than a typed one, so a hint
 *  the operator legitimately entered could come back changed or missing. The server trims it
 *  and the pipeline treats it as a hint; neither is owed a well-formed one. */
function readSessionSetHint(): string {
  return readSession(SESSION_KEYS.setHint) ?? ''
}

/** The claim as stored: a JSON list of finish strings, or `[]` for anything else.
 *
 *  NOT VALIDATED HERE, because the vocabulary this must be checked against is per-game and
 *  arrives from `GET /games` after the first render — see the effect that drops a claim the
 *  chosen game does not stock. A remembered `reverse_holo` means nothing under Riftbound,
 *  and sending it would earn a `variant_invalid` refusal mid-run with a card at the lens.
 *
 *  A BARE STRING READS AS ONE MEMBER, which `readSessionRarityClaim` below needs no clause
 *  for and this one does. The key held a bare string until D3's amendment of 2026-08-23, so
 *  every capture tab open at that moment has one under it right now; without this line the
 *  first reload after the change starts a run with the claim silently gone — which is the
 *  failure D27 exists to prevent, on the screen where a lost claim costs a review tap per
 *  card for the rest of the stack. It is the same read-side backfill the sidecar, the
 *  record and the wire all do, applied to the one store nothing else can reach.
 *
 *  Junk collapses to the empty claim rather than to a partial one, and non-string members
 *  are dropped rather than failing the whole list — `readSessionRarityClaim`'s rules, for
 *  its reasons, because the two claims are one shape now (D3). */
function readSessionFinish(): FinishClaim {
  const stored = readSession(SESSION_KEYS.finish)
  if (stored === null) return []
  try {
    const parsed: unknown = JSON.parse(stored)
    if (typeof parsed === 'string') return [parsed]
    if (!Array.isArray(parsed)) return []
    return parsed.filter((member): member is string => typeof member === 'string')
  } catch {
    /* Not JSON at all — which is exactly what a pre-amendment tab holds, since a bare
     * `reverse_holo` was written unquoted. One member, not six letters and not nothing. */
    return [stored]
  }
}

/** Likewise unvalidated here and checked against the registry when it lands: a key that was
 *  real this morning can be gone after somebody edits `pipeline/games.py` and restarts. */
function readSessionGame(): string | null {
  return readSession(SESSION_KEYS.game)
}

/** The stack claim as stored: a JSON list of rarity strings, or `[]` for anything else.
 *
 *  JUNK COLLAPSES TO THE EMPTY CLAIM, never to a partial one. A hand-edited value, a bare
 *  string, a list with a number in it — each of those is a store this session cannot trust,
 *  and "the operator claimed nothing" is the state the run starts in and the only safe
 *  reading (D3's no-claim instinct applied to D23's claim). Non-string members are dropped
 *  rather than failing the whole list because a mixed list has string members the operator
 *  really did claim; membership in the CHOSEN GAME's vocabulary is not checked here, for
 *  the same reason `readSessionFinish` does not — the vocabulary arrives from `GET /games`
 *  after the first render, and the effect beside the finish one drops what the registry
 *  disowns. */
function readSessionRarityClaim(): string[] {
  const stored = readSession(SESSION_KEYS.rarityClaim)
  if (stored === null) return []
  try {
    const parsed: unknown = JSON.parse(stored)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((member): member is string => typeof member === 'string')
  } catch {
    return []
  }
}

/* A SHAPE FLOOR, NOT A MIRROR of what `newCaptureId` mints. It produces a UUID by both of its
 * paths, and an exact UUID test here would silently start discarding held ids the day that
 * function's format changed — discarding a held id being the exact failure this whole block
 * exists to prevent. So: id-shaped characters, a plausible length, nothing else.
 *
 * It is worth refusing anything at all because the server accepts any non-empty string as a
 * `capture_id` and writes it onto the record. A hand-edited value cannot be an id the server
 * ever committed under — this app is the only thing that mints them — so dropping it loses no
 * ambiguity that was ever resolvable, and keeping it would put junk in `inventory.json`. */
const CAPTURE_ID_SHAPE = /^[A-Za-z0-9-]{8,64}$/

function readSessionCaptureId(): string | null {
  const stored = readSession(SESSION_KEYS.captureId)
  return stored !== null && CAPTURE_ID_SHAPE.test(stored) ? stored : null
}

function describe(err: unknown): Note {
  // The server's own message, unchanged. docs/DESIGN.md's copy rules already reach these
  // strings — they say what happened and what to do next — and rewording them into
  // something friendlier makes them less actionable, not more.
  if (err instanceof ServerError) return { text: err.message, code: err.code }
  if (err instanceof Error) return { text: err.message, code: null }
  return { text: String(err), code: null }
}

function photoSrc(box: number, index: number, revision: number): string {
  /* A position can hold different bytes than it did five seconds ago: undo hard-deletes the
   * photo and releases the index, and the next capture into that box takes it back. The URL
   * is identical either way, so a cached image shows the card that was just deleted.
   *
   * On this screen that is not a cosmetic bug. The reason you undo is that the photo was
   * bad; you re-shoot, and the panel shows you the bad photo again, at the one moment the
   * whole layout exists to let you judge it.
   *
   * `server.ts` argues against a cache-busting parameter and it is right about the two
   * things it names: minting one inside `photoUrl` would thread it through every caller and
   * would defeat caching for the pull preview, which wants neither. Neither applies to one
   * caller doing it locally, and the fix that module recommends — a cache header from the
   * server — is a change to a file this session does not own. If that header lands, this
   * function is what should be deleted.
   */
  const url = photoUrl(box, index)
  return `${url}${url.includes('?') ? '&' : '?'}v=${revision}`
}

function blurActive(): void {
  // A trigger ignores keys typed into an input, a textarea or a select — correctly, since
  // typing a set name must not photograph five cards. The cost is that focus left in a field
  // makes C and U dead keys, and a dead key at a rig reads as a broken app. So Enter hands
  // focus back rather than leaving the operator pressing a key nothing is listening for.
  if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
}

/* ---- the sidebar's whole grammar: the hairline row, and what an open one holds ----
 *
 * Pass D, approved by the owner 2026-08-23 ("D is approved — proceed") after four rendered
 * alternatives and a critique. Every field is ONE line at rest — key chip, label, current
 * value right-aligned in the utility face — and opening one expands it in place, closing
 * whatever else was open. The chip rows this replaces drew every choice all the time, which
 * is exactly what the owner's "oversized boxes" complaint was about: five games, four
 * finishes and a box list were on permanent display for claims that are set once per stack.
 * A closed row spends 32px saying what IS chosen; the choosing costs one keypress.
 *
 * WHAT THE HYBRID TRADES AWAY, carried over from the mockup because the honesty is the
 * point: selection is drawn two ways now — the ink-filled square in option lists and the
 * rarity bitfield, weight-plus-rail inside a segmented track — and that second language is
 * the direct price of putting a track inside a disclosure. Writing costs two keys where a
 * wall of chips cost one, and comparing two fields costs two openings. Both were argued to
 * the owner on the mockup itself and accepted with it.
 *
 * `aria-expanded` on every row and `aria-pressed` on every option are facts about the
 * document, and the stylesheet selects on them rather than on state classes — the same
 * cannot-drift argument App.tsx makes for `aria-current`.
 */

/** Which field is open. One at a time, by construction: the state is a single id, so a
 *  second field cannot be open without closing the first — the mockup's rule enforced by
 *  the type rather than by bookkeeping. */
type FieldId = 'box' | 'set' | 'rarity' | 'finish' | 'game' | 'camera' | 'rotation' | 'trigger'

/* The field letters, none of which may be `c` or `u` — those are the run's own keys and
 * stay reserved (see CAPTURE_KEY). `v` for the camera because `c` is taken, and `o` for
 * rotation because `r` is: the mnemonic bends before the shutter does. The `,` leader
 * chord (App.tsx) is consumed in the capture phase before any of these are offered a key,
 * so `,` then `b` navigates and does not also open the box field. */
const FIELD_KEYS: Readonly<Record<string, FieldId>> = {
  b: 'box',
  s: 'set',
  r: 'rarity',
  f: 'finish',
  g: 'game',
  v: 'camera',
  o: 'rotation',
  t: 'trigger',
}

/* The fourth copy of the editable-target predicate in this app, after trigger.ts,
 * ReviewQueue.tsx and App.tsx — PullPreview.tsx records that the hoist is due, and App.tsx
 * records why it has not happened (the shared module needs a docs/map.py entry, which is a
 * commit made on purpose). Same members for the same reasons: SELECT because its letter
 * typeahead makes a focused native picker a real collision, contentEditable for
 * completeness. A field letter typed into the set hint must be a letter. */
function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}

/** A field at rest: key chip · label · whatever the field puts on the right. A button,
 *  because the whole line is the control that opens it — a 32px-tall target rather than a
 *  chevron to hunt for. */
function Row({
  k,
  label,
  right,
  onToggle,
}: {
  k: string
  label: string
  right: ReactNode
  onToggle: () => void
}) {
  return (
    <button type="button" className="capture-row" aria-expanded={false} onClick={onToggle}>
      <span className="capture-k">{k}</span>
      <span className="capture-lab">{label}</span>
      {right}
    </button>
  )
}

/** The one open field: the same row as its head (now closing, `aria-expanded` true, meta on
 *  the right instead of the value), a 2px ink rail down the left edge, and the field's own
 *  body under it. The rail is flush to the panel edge — the stylesheet's negative margin —
 *  so an open field reads as a state of the column, not a nested card. */
function OpenField({
  k,
  label,
  meta,
  onClose,
  children,
}: {
  k: string
  label: string
  meta: ReactNode
  onClose: () => void
  children: ReactNode
}) {
  return (
    <div className="capture-open">
      <button type="button" className="capture-row" aria-expanded={true} onClick={onClose}>
        <span className="capture-k">{k}</span>
        <span className="capture-lab">{label}</span>
        <span className="capture-meta">{meta}</span>
      </button>
      {children}
    </div>
  )
}

/** One option row inside an open field: digit chip (or none), the 12px selection mark,
 *  the name, an optional machine trail on the right.
 *
 *  KEYLESS PAST NINE IS DELIBERATE, not a truncation: digits 1–9 are the only single
 *  keystrokes there are, a tenth needs a modifier or a two-key sequence, and the review
 *  queue already set the precedent — rows past the ninth draw no chip rather than a chip
 *  that does nothing. One filter keystroke re-indexes the survivors into digit reach,
 *  which is why no field here ever needs a tenth key. */
function Opt({
  k,
  on,
  name,
  sfx,
  trail,
  onPick,
}: {
  k?: string
  on: boolean
  name: string
  /** The de-emphasised shared suffix — ` Rare` on eleven of Pokemon's thirteen. Even on a
   *  selected row the suffix never takes the weight, so the eye lands on Radiant /
   *  Illustration / Hyper: the word that distinguishes, not the word they share. */
  sfx?: string | null
  trail?: string
  onPick: () => void
}) {
  return (
    <button type="button" className="capture-opt" aria-pressed={on} onClick={onPick}>
      <span className="capture-k">{k ?? ''}</span>
      <span className="capture-mark" />
      <span className="capture-opt-name">
        {name}
        {sfx == null ? null : <span className="capture-sfx">{sfx}</span>}
      </span>
      {trail === undefined ? null : <span className="capture-opt-trail">{trail}</span>}
    </button>
  )
}

/** A's segmented track, alive only inside a disclosure — the mockup's rule, kept: one
 *  bordered box subdivided by hairlines, for single-selects whose whole vocabulary fits one
 *  line (finish ≤4, rotation 4, trigger 2). Cells are content-sized with no flex-grow, so a
 *  vocabulary swapping four members for three shortens the track without moving a surviving
 *  cell — the reflow that killed the all-chips pass in review.
 *
 *  `aria-pressed` buttons in a named group rather than a radiogroup of radios: the rest of
 *  this screen's options are pressed-state buttons, and one selection semantics is worth
 *  more than the purer ARIA pattern — a radio that cannot arrow-navigate is a worse lie
 *  than a button that says pressed.
 *
 *  A disabled cell stays rendered — `aria-disabled`, dimmed, refusing the click — never
 *  hidden: the operator must be able to see what a rarity claim cost, or the claim reads as
 *  the screen losing a finish. WCAG exempts disabled controls from the contrast floor, and
 *  the cell's own `not stocked` sentence is drawn at full contrast under the track. */
function Track({
  label,
  cells,
}: {
  label: string
  cells: readonly {
    text: string
    on: boolean
    disabled?: boolean
    onPick: () => void
  }[]
}) {
  return (
    <div className="capture-trackline">
      <span />
      <div className="capture-track" role="group" aria-label={label}>
        {cells.map((cell) => (
          <button
            key={cell.text}
            type="button"
            className="capture-cell"
            aria-pressed={cell.on}
            aria-disabled={cell.disabled === true ? true : undefined}
            onClick={() => {
              if (cell.disabled !== true) cell.onPick()
            }}
          >
            {cell.text}
          </button>
        ))}
      </div>
    </div>
  )
}

/** `Radiant Rare` → `Radiant` + a de-emphasised ` Rare`. The bare `Rare` keeps its whole
 *  name — there is no stem left if the suffix is taken from it. Rendering only; the string
 *  compared, claimed and sent is always the export's exact cell (D22). */
function rarityNameParts(name: string): [string, string | null] {
  return name !== 'Rare' && name.endsWith(' Rare') ? [name.slice(0, -5), ' Rare'] : [name, null]
}

export function CaptureScreen() {
  const camera = useCamera()

  /* THE REGISTRY, FETCHED — never mirrored in a `games.ts` on this side. `pipeline/games.py`
   * is hand-authored and audited against the committed exports; a second copy here would be
   * hand-authored and audited by nobody. `GET /games` is the whole of what the app knows
   * about what a game is. */
  const [registry, setRegistry] = useState<GameRegistry | null>(null)
  const [registryNote, setRegistryNote] = useState<Note | null>(null)

  // Box, game, set hint and finish are client state resent on every capture (spec 5.2). The
  // server holds no notion of a current box, which is what lets two devices work without a
  // session.
  //
  // ALL FOUR ARE RESTORED FROM `sessionStorage` ON THE FIRST RENDER (D27). Passing the reader
  // rather than calling it — `useState(readSessionBox)` — is what keeps it to the first
  // render: an initialiser expression is evaluated every render and thrown away, and this one
  // touches a synchronous store. The restored value is validated; see the readers.
  const [box, setBox] = useState<number | null>(readSessionBox)
  // The draft is NOT restored, and that is the distinction the whole carve-out rests on: a
  // half-typed box number is not a claim the operator has made. Restoring one would put a
  // number in the field that has never been submitted and does not agree with `box` above.
  const [boxDraft, setBoxDraft] = useState('')
  const [boxNote, setBoxNote] = useState<string | null>(null)
  const [setHint, setSetHint] = useState(readSessionSetHint)
  // EMPTY, not ['normal']. See NO_CLAIM_LABEL above: the default has to be "the operator
  // has said nothing", or D3's rungs 2 and 3 are dead for every card this rig ever sees.
  // A SET since the amendment of 2026-08-23 — any number of members is legal, including all
  // of them, and toggling the last one off IS the clear, exactly as the rarity claim beside
  // it behaves. That sameness is D3's stated point, not a coincidence of implementation.
  const [finish, setFinish] = useState<FinishClaim>(readSessionFinish)

  /* D23's stack claim: which of the chosen game's rarities this pre-sorted stack may hold.
   * Empty is NO CLAIM — the wire omits the key, the sidecar records nothing, and the ladder
   * walks exactly as it did before the field existed. Any number of members is legal,
   * including all of them; toggling the last one off IS the clear, so the control needs no
   * separate reset. Restored from `sessionStorage` (D27) and validated against the registry
   * by the effect beside the finish one, exactly as the finish claim is. */
  const [rarityClaim, setRarityClaim] = useState<string[]>(readSessionRarityClaim)

  /* WHICH FIELD IS OPEN, or null for the all-at-rest column. One id rather than a set —
   * pass D's one-field-open rule enforced by the shape of the state. Session-only and
   * deliberately not persisted: an open picker is a moment, not a claim. */
  const [openField, setOpenField] = useState<FieldId | null>(null)

  // The two filter drafts. Cleared whenever the open field changes: a filter is an aid to
  // one opening, and a remembered one would re-narrow a list the operator cannot see yet.
  const [boxFilter, setBoxFilter] = useState('')

  /* WHICH GAME THE NEXT CARD IS. Null only until the registry arrives — it is then set to
   * the registry's own `default`, and nothing on this screen can put it back to null.
   *
   * NULL IS NOT A NO-CLAIM HERE, and the difference from `finish` two lines up is D21's,
   * spelled out because the two controls sit next to each other and look alike. A null
   * finish is a real state with a ladder underneath it that infers one. There is no ladder
   * that infers a game, so a null game is not "no claim" — it is "the app has not been told
   * what the games are yet", and the only honest thing to do in that state is not capture.
   *
   * THE DEFAULT COMES FROM THE SERVER, not from a `'pokemon'` written here. Hardcoding it
   * would be a second decision that has to agree with `games.DEFAULT_GAME` for ever.
   *
   * A RESTORED KEY IS A CLAIM ABOUT A REGISTRY THIS RENDER HAS NOT SEEN (D27), so it is held
   * exactly as long as the registry agrees with it — `loadGames` drops it otherwise. Without
   * that check the paragraph above stops being true: `gameEntry` could be null after a
   * successful load, which every guard on this screen reads as "the list has not arrived
   * yet" and which would leave capture blocked behind a sentence about waiting for a server
   * that had already answered. */
  const [game, setGame] = useState<string | null>(readSessionGame)

  /* The note on the LAST capture, and this is the only control on the screen that writes to
   * a card other than the one about to be photographed. `noteBusy` is deliberately separate
   * from `busy`: `busy` gates the shutter and counts swallowed trigger fires, and a save
   * that blocked the trigger would drop feeder cards while somebody typed. */
  const [noteDraft, setNoteDraft] = useState('')
  const [noteBusy, setNoteBusy] = useState(false)
  const [noteSaved, setNoteSaved] = useState<(Note & { done: boolean }) | null>(null)

  // The server's own high-water mark per box, from GET /status. Display only — the docstring
  // on `Inventory.next_index` says so, and the allocator takes no index for exactly that
  // reason. Kept current locally rather than refetched after every capture: a round trip per
  // card at a rig that fires every few seconds buys nothing a reload cannot fix.
  const [nextIndex, setNextIndex] = useState<Record<string, number>>({})
  const [statusNote, setStatusNote] = useState<Note | null>(null)

  const [shots, setShots] = useState<Shot[]>([])
  const [halt, setHalt] = useState<Halt | null>(null)
  const [busy, setBusy] = useState(false)
  // `position` is the rendered label of what was deleted, shown separately from `text` so it
  // can carry the utility face inside a body sentence. Null on a refusal, where the whole
  // message is the server's own and names its own position.
  const [undoNote, setUndoNote] = useState<
    (Note & { done: boolean; position: string | null }) | null
  >(null)
  const [revision, setRevision] = useState(0)

  // The position a replayed capture came back with, or null. Set only when the server
  // answers `created: false` — see the capture path below for why that is the payoff of
  // holding the capture id rather than a curiosity.
  const [replayed, setReplayed] = useState<string | null>(null)

  /* Which trigger is behind the seam. SESSION-ONLY, never persisted — deliberately unlike
   * the camera choice and the rotation chip, both remembered per device. A remembered
   * camera cannot take a photo on its own; a remembered MOTION mode arms an automatic
   * shutter on page load, pointed at whatever happens to be in front of the lens, with
   * nobody having asked for it this session. Arming the trigger is starting the run, so it
   * is an act, not a setting. */
  const [triggerMode, setTriggerMode] = useState<'manual' | 'motion'>('manual')

  // The machine's own counters and live signal, for the HUD. Null until the first frame
  // reaches the machine, which is also the "is it actually seeing anything" indicator.
  const [motionDiag, setMotionDiag] = useState<MotionDiagnostics | null>(null)

  /* Fires the SCREEN declined, by reason. The trigger's own suppressions (same card, empty
   * stand) live in the machine's counters; these are the seam's other half — the trigger
   * fired and the screen's guards ate it. Under a key that silence is fine, because the
   * finger that pressed is attached to someone watching the screen. Under a feeder it is
   * spec 5.5's exact failure: every entry here is a card that may have passed the lens
   * unrecorded, so the count is rendered loudly rather than kept as a curiosity. */
  const [swallowed, setSwallowed] = useState<{
    busy: number
    halted: number
    noBox: number
    notReady: number
    held: number
  }>({ busy: 0, halted: 0, noBox: 0, notReady: 0, held: 0 })

  /* A mode change starts a fresh accounting period. Arming builds a fresh machine, so a
   * HUD still showing the dead session's counters would render numbers no live machine
   * owns — and the swallowed counts belong to the run that swallowed them, not to the
   * session. Both zero together or the two halves of the readout desynchronise. */
  const switchTrigger = useCallback(
    (mode: 'manual' | 'motion') => {
      /* SETTING THE MODE IT IS ALREADY IN IS NOT A MODE CHANGE, and the chip row sends one
       * every time the pressed chip is pressed — which is an ordinary thing to do at a rig
       * while checking that motion really is armed.
       *
       * Unguarded, that press was destructive in two ways at once, and neither said so. The
       * seam holds the same trigger, so `captureTrigger`'s identity does not change and the
       * effect below does not re-arm: the MACHINE keeps its cumulative fires, same, empty
       * and stall. Everything else in this function ran anyway — the swallowed counts were
       * zeroed under a machine that had not restarted, which is exactly the desync the
       * paragraph below forbids, and `traceRef` was replaced with an empty recording, taking
       * a feeder pass's worth of tuning data with it and leaving a HUD still reporting the
       * fires that produced it.
       *
       * So the guard is first, before anything is reset. */
      if (mode === triggerMode) return

      setTriggerMode(mode)
      setMotionDiag(null)
      setSwallowed({ busy: 0, halted: 0, noBox: 0, notReady: 0, held: 0 })
      // The trace belongs to one armed session, exactly like the machine's own counters:
      // arming starts a fresh recording, disarming keeps the old one around so it can
      // still be saved after the run stops.
      if (mode === 'motion') traceRef.current = new MotionTrace(DEFAULT_PARAMS)
    },
    [triggerMode],
  )

  /* D19's Tier-1 tuning instrument. A ref, not state: it takes ~30 writes a second and
   * nothing re-renders on its account — the HUD's frame counter already moves via the
   * throttled diagnostics. */
  const traceRef = useRef<MotionTrace | null>(null)

  // Read synchronously inside the capture path. React state cannot serve here: two fires in
  // one tick — a key repeat, or a focused button activated by the same press — would both
  // read the stale `false` and send two photos of one card.
  const busyRef = useRef(false)

  /* The id of the photograph in flight, held across a halt and cleared only when the server
   * has answered. THIS REF IS THE RETRY GUARD (spec 5.5); without it there is none.
   *
   * The id used to be minted inline in the call argument, which meant no code path could
   * ever resend one — so the server's replay branch and every reader of `created` were dead
   * code, and the guard looked covered while guarding nothing. What that costs is the worst
   * failure this screen has: the server commits and the response is lost, leaving a record
   * and a photo at index N for a card that is not in the box. Re-shoot and the card is
   * recorded twice; skip it and every card after it sits one physical slot from its recorded
   * position for the rest of the box, which is the one thing D10's positions cannot survive.
   *
   * A ref rather than state, for the same reason `busyRef` is one: it is read and written
   * inside the capture path, where a value that only updates on the next render is a value
   * that is wrong exactly when it matters.
   *
   * AND IT IS MIRRORED INTO `sessionStorage` (D27), which is the reason that decision exists.
   * A ref does not survive a reload, and a reload during a halt is not an exotic event: it is
   * what an operator does to a screen that looks stuck. Losing the id there does not lose a
   * setting, it makes the ambiguity permanently unresolvable — the server may hold a record
   * and a photograph at index N for a card that never went in the box, and nothing afterwards
   * can tell. `rememberCaptureId` below is the only writer, so the ref and the store cannot
   * come apart.
   */
  const captureIdRef = useRef<string | null>(readSessionCaptureId())

  /* Whether the id in that ref came back from a reload rather than being minted this session.
   * State, because it is rendered; set once and only ever cleared.
   *
   * IT IS NOT A CURIOSITY, IT IS THE OTHER HALF OF PERSISTING THE ID. A held id changes what
   * the next press of the shutter means — the server ignores the image on a replay and
   * answers with the card it already committed — so a fire with the WRONG card at the lens
   * answers for the held card and lets the new one past unrecorded. The halt banner is what
   * normally says so, and the halt is deliberately not persisted, so after a reload nothing
   * on this screen would say it. Restoring the id silently would trade one unresolvable
   * ambiguity for a quieter one. */
  const [heldAcrossReload, setHeldAcrossReload] = useState(() => captureIdRef.current !== null)

  /** The one writer of the in-flight capture id: ref first, store second, never one without
   *  the other. `useCallback` with no dependencies so `doCapture`'s identity does not change
   *  per render — the trigger seam re-arms on that identity. */
  const rememberCaptureId = useCallback((id: string | null) => {
    captureIdRef.current = id
    writeSession(SESSION_KEYS.captureId, id)
    // Whatever this id's history, it is this session's business from here: either it has
    // just been answered, or a fresh one has been minted for a photograph taken now.
    if (id === null) setHeldAcrossReload(false)
  }, [])

  /* THE FOUR CLAIMS, MIRRORED. One effect rather than four, because they are one decision —
   * D27's list — and a per-field writer would be four places for a fifth field to be
   * forgotten in. Cheap enough to run on a keystroke in the set hint field: five string
   * writes into a synchronous store, against a JPEG encode on the same screen.
   *
   * Effects rather than writes at each call site, and that is the part worth defending: `box`
   * is set from the chip row and from the box form, `finish` from the chip row, from
   * `pickGame` and from the vocabulary check below. A writer at each of those is a writer
   * somebody forgets at the next one, and a claim that is on screen but not in the store is
   * exactly the silent disagreement this whole block is trying to end. */
  useEffect(() => {
    writeSession(SESSION_KEYS.box, box === null ? null : String(box))
    writeSession(SESSION_KEYS.setHint, setHint.trim() === '' ? null : setHint)
    // Empty stored as absent, and a non-empty claim as JSON — the rarity claim's rule five
    // lines down, for its reason, now that both claims are lists.
    writeSession(
      SESSION_KEYS.finish,
      finish.length === 0 ? null : JSON.stringify(finish),
    )
    writeSession(SESSION_KEYS.game, game)
    // Empty is stored as absent, the same rule the wire applies: an empty claim is NO
    // claim, and a stored `[]` would be a record of nothing that still has to be read.
    writeSession(
      SESSION_KEYS.rarityClaim,
      rarityClaim.length === 0 ? null : JSON.stringify(rarityClaim),
    )
  }, [box, setHint, finish, game, rarityClaim])

  const loadStatus = useCallback(async () => {
    try {
      const status = await getStatus()
      setNextIndex(status.next_index ?? {})
      setStatusNote(
        status.next_index === null
          ? {
              text:
                status.problem ??
                'The server could not list the boxes in use. Positions cannot be allocated until that is corrected.',
              code: null,
            }
          : null,
      )
    } catch (err) {
      setStatusNote(describe(err))
    }
  }, [])

  useEffect(() => {
    void loadStatus()
  }, [loadStatus])

  /* THE REGISTRY, ONCE. Not polled, unlike `/status`: it changes when somebody edits a
   * Python file and restarts the server, which is not something a capture session watches
   * for. A failure leaves `game` null and therefore blocks capture — see `blocked` below —
   * which is the honest outcome, because a capture with no game is a record no join can
   * ever resolve. The note carries the server's own words and a way to ask again. */
  const loadGames = useCallback(async () => {
    try {
      const answer = await getGames()
      setRegistry(answer)
      setRegistryNote(null)
      /* THE SERVER'S DEFAULT, and only while nothing the registry still carries has been
       * chosen. `setGame(prev => ...)` rather than a bare set so that a refetch — the
       * operator pressing "Ask again" after a restart — cannot silently move a running
       * session back to Pokemon.
       *
       * THE MEMBERSHIP TEST IS D27's, and it is what keeps `gameEntry === null` meaning "the
       * registry has not arrived". `game` used to be settable only from `answer.default` or
       * from a chip built out of `answer.games`, so a key the server does not serve was
       * unreachable; a key restored from `sessionStorage` is not, and neither is one that was
       * valid until somebody edited `pipeline/games.py` and restarted between two captures.
       * Falling back to the default rather than to null, because null blocks capture behind a
       * sentence about waiting for a server that has already answered. */
      setGame((prev) =>
        prev !== null && answer.games.some((entry) => entry.key === prev) ? prev : answer.default,
      )
    } catch (err) {
      setRegistryNote(describe(err))
    }
  }, [])

  useEffect(() => {
    void loadGames()
  }, [loadGames])

  /** The chosen game's entry, or null while the registry is still on its way.
   *
   *  Null after a successful load would mean the server named a game it does not serve,
   *  which cannot happen — `game` is only ever set from `registry.default` or from a chip
   *  built out of `registry.games`. */
  const gameEntry = useMemo<GameEntry | null>(
    () => registry?.games.find((entry) => entry.key === game) ?? null,
    [registry, game],
  )

  /* Changing the game CLEARS THE FINISH CLAIM AND THE RARITY CLAIM, and leaves the box and
   * the set hint alone.
   *
   * The finish, because `finishes` is per-game: `holo` is a Pokemon string, and a claim of
   * `reverse_holo` carried into a game whose enum has no such member would be sent to the
   * server and refused as `variant_invalid` at the worst possible moment — mid-run, with a
   * card at the lens. Clearing it is also right on its own terms: a finish claimed about a
   * Pokemon stack says nothing about the Yu-Gi-Oh card that follows it.
   *
   * The rarity claim for both of the same reasons, one wire code over: the members are the
   * game's own Rarity cells (D22, verbatim), so under any other game they would be refused
   * as `rarity_claim_invalid` — and a claim about a sorted Pokemon stack is not a claim
   * about whatever game follows it.
   *
   * The box, because a box is a physical drawer and D21 makes MIXED BOXES LEGAL — that is
   * the whole point of the game being a per-card claim rather than a session mode. Clearing
   * it would make the operator re-pick a drawer they have not put down.
   *
   * The set hint, because it is free text the operator typed and this screen does not get
   * to decide it has gone stale. A hint that no longer applies costs one review-queue tap;
   * a hint silently erased between two cards of the same stack costs a whole stack of them.
   */
  const pickGame = useCallback((key: string) => {
    setGame(key)
    setFinish([])
    setRarityClaim([])
  }, [])

  /* WHAT THE CLAIMED RARITIES LEAVE CLAIMABLE — D23's narrowing, job b. The offered finish
   * set is the UNION of `finish_by_rarity[r]` over the claimed rarities: a stack claimed
   * `Common + Double Rare` may still be claimed `holo`, because one of its members may be.
   * An empty claim narrows nothing — null here means "no narrowing", which is not the same
   * value as "narrowed to everything" and keeps the excluded-cell rendering honest.
   *
   * FAILS OPEN on a claimed rarity the matrix has no row for. The registry validates that
   * every rarity has one, so the case is a registry bug or a mid-session restart — and the
   * matrix's own rule (a superset, so a legitimate stack is never unclaimable) says the
   * safe direction is to narrow less, never more. A missing row treated as "contributes
   * nothing" would exclude every finish and render a track of dead cells. */
  const offeredFinishes = useMemo<ReadonlySet<string> | null>(() => {
    if (gameEntry === null || rarityClaim.length === 0) return null
    const rows = rarityClaim.map((rarity) => gameEntry.finish_by_rarity[rarity])
    if (rows.some((row) => row === undefined)) return null
    const union = new Set<string>()
    for (const row of rows) for (const member of row ?? []) union.add(member)
    return union
  }, [gameEntry, rarityClaim])

  /* THE SAME RULE, ENFORCED AGAINST A CLAIM NOBODY PICKED. `pickGame` clears the finish when
   * the operator changes game, which covers every path that existed before D27; a claim
   * restored from `sessionStorage` arrives without anyone having touched the picker, and so
   * does one left standing when a server restart changes what a game stocks. Both end the
   * same way — a `reverse_holo` sent under a game whose enum has no such member is refused as
   * `variant_invalid` at the worst possible moment, mid-run with a card at the lens.
   *
   * Falls back to no claim rather than to the nearest thing the game does stock, which would
   * be inventing a claim: D3 rung 1 treats the toggle as a claim the operator made, and no
   * claim is the state every run starts in. A game with an empty vocabulary — `misc` — draws
   * no Finish field at all, and this is what makes sure nothing is being sent behind it.
   *
   * THE NARROWING CLAUSE IS THE SAME FALLBACK ONE CLAIM LATER (D23): a finish the rarity
   * claim excludes falls back to no claim rather than surviving as a claim the track now
   * draws unselectable — a selected cell the operator cannot re-select is a state the
   * screen cannot explain. And it only ever CLEARS: when the narrowing leaves exactly one
   * selectable finish it is not auto-claimed, because an inferred claim is precisely what
   * D3 rung 1 says a claim is not.
   *
   * It cannot fight the operator: the only states it changes are ones the track cannot
   * produce, since the track offers only `gameEntry.finishes` and refuses excluded cells. */
  useEffect(() => {
    if (finish.length === 0 || gameEntry === null) return
    /* A GAME THAT DRAWS NO FINISH FIELD MAY NOT CARRY A FINISH CLAIM, and this is the case
     * the membership check above cannot see: `pokemon_code` stocks `normal`, so a `normal`
     * claimed under Pokemon is a MEMBER of the new game's enum and survives the line above
     * — while the control that could take it back has just stopped being drawn (the field
     * renders only at two or more finishes, per the owner's 2026-08-23 ruling). The claim
     * would then ride invisibly onto every capture of the run, which is worse than the
     * auto-selection D23 refuses: at least an auto-selected claim is on screen. */
    if (gameEntry.finishes.length < 2) {
      setFinish([])
      return
    }
    /* MEMBER-WISE SINCE D3's AMENDMENT (2026-08-23), and the rarity effect below is NOT a
     * template that can be copied verbatim here — it has no analogue of the hazard in the
     * next paragraph, because a one-member rarity claim still only filters.
     *
     * NARROWING A CLAIM OF TWO OR MORE DOWN TO ONE CLEARS IT INSTEAD. A one-member finish
     * claim DETERMINES: it outranks the catalog at rung 2 and is what detection is
     * cross-checked against at rung 3. So silently keeping the survivor of `{normal, holo}`
     * would manufacture a determining claim the operator never made, out of a filtering one
     * they did — auto-selection by the back door, and D23 refuses auto-selection in words
     * ("it never auto-selects, not even when one finish is left") for exactly this reason.
     * Two or more survivors are kept, because a narrower filter is still a filter and still
     * something the operator said.
     *
     * Falling back to NO claim rather than to the nearest thing the game stocks is the same
     * rule this effect always had: D3 rung 1 treats the control as a claim the operator
     * made, and no claim is the state every run starts in. The whole row reads `no claim`
     * when it happens, so the loss is on screen rather than silent. */
    const kept = finish.filter(
      (member) =>
        gameEntry.finishes.includes(member) &&
        (offeredFinishes === null || offeredFinishes.has(member)),
    )
    if (kept.length !== finish.length) setFinish(kept.length <= 1 ? [] : kept)
  }, [finish, gameEntry, offeredFinishes])

  /* The rarity claim's copy of the effect above, for the same two arrivals — a restored
   * claim, and a registry restart that renamed a rarity. Members the chosen game does not
   * author are DROPPED, not the whole claim: the surviving members are claims the operator
   * really made about this stack, and `rarity_claim_invalid` mid-run is the failure this
   * exists to head off. Mirrors `readSessionRarityClaim`'s member-wise salvage. */
  useEffect(() => {
    if (gameEntry === null || rarityClaim.length === 0) return
    /* A GAME THAT DRAWS NO RARITY FIELD MAY NOT CARRY A RARITY CLAIM — the finish row's
     * rule, for the finish row's reason. A one-rarity game passes the membership filter
     * below whenever the claim happens to be that rarity, so without this the claim would
     * survive onto a screen with no control to take it back. */
    if (gameEntry.rarities.length < 2) {
      setRarityClaim([])
      return
    }
    const kept = rarityClaim.filter((member) => gameEntry.rarities.includes(member))
    if (kept.length !== rarityClaim.length) setRarityClaim(kept)
  }, [rarityClaim, gameEntry])

  /* Toggle one rarity in or out — and REBUILD THE LIST IN STACK ORDER whichever way the
   * toggle went. The claim is rendered as the bitfield and written into the sidecar, and
   * both should read in the catalog's own order however the operator happened to tap:
   * `games.py` says stack order is the point of the list, and a claim stored in tap order
   * would put the same four rarities in a different order per session. */
  /* Toggle one finish in or out — and REBUILD THE LIST IN THE GAME'S ENUM ORDER whichever
   * way the toggle went, which is `toggleRarity` below with a different order to impose.
   * `pipeline/variant.py:_check_claim`, `identify/sidecar.py:_check_variant` and the capture
   * route all canonicalise to that same order; doing it here as well means the claim leaves
   * this screen already in the form everything downstream will put it in, so two identical
   * claims tapped in different orders are one value and a restated correction diffs as no
   * change rather than churning a sidecar and a history line. */
  const toggleFinish = useCallback(
    (member: string) => {
      const order = gameEntry?.finishes ?? []
      setFinish((prev) => {
        const next = prev.includes(member)
          ? prev.filter((f) => f !== member)
          : [...prev, member]
        return order.filter((f) => next.includes(f))
      })
    },
    [gameEntry],
  )

  const toggleRarity = useCallback(
    (name: string) => {
      const order = gameEntry?.rarities ?? []
      setRarityClaim((prev) => {
        const next = prev.includes(name) ? prev.filter((r) => r !== name) : [...prev, name]
        return order.filter((r) => next.includes(r))
      })
    },
    [gameEntry],
  )

  const boxes = useMemo(
    () =>
      Object.keys(nextIndex)
        .map((key) => Number(key))
        .filter((value) => Number.isInteger(value))
        .sort((left, right) => left - right),
    [nextIndex],
  )

  const nextForBox = box === null ? undefined : nextIndex[String(box)]

  // Information, not a confirmation step. The owner was offered a confirmation on a new box
  // and declined it (spec 5.2), and this does not reinstate one: nothing is blocked and
  // nothing is dismissed. It is also the earlier of the two chances to catch a typed 33 for
  // 3 — the server's own `new_box` flag arrives after a photo has already been written.
  const boxIsEmpty = box !== null && (nextForBox === undefined || nextForBox <= 1)

  /* ---- the open field's machinery: who is open, what its filter shows, where focus goes ---- */

  const closeField = useCallback(() => setOpenField(null), [])

  const toggleField = useCallback((id: FieldId) => {
    setOpenField((prev) => (prev === id ? null : id))
  }, [])

  // A filter belongs to one opening. Cleared on every change of `openField` — including to
  // null — so no field ever reopens pre-narrowed by a search the operator cannot see the
  // reason for. `boxNote` rides along: it explains one rejected draft, not a field.
  useEffect(() => {
    setBoxFilter('')
    setBoxNote(null)
  }, [openField])

  /* The two filter inputs and the new-box entry, focused when their field opens. Focus goes
   * to the FILTER, which is what makes "thirty boxes cost what three cost" true as typed:
   * B, digits, Enter, with no click in between. The cost is that a focused input eats the
   * field letters (they are typing) — Esc still closes from inside an input, deliberately,
   * because it types nothing and a trap that needs a mouse to leave is worse than an
   * inconsistent key. */
  const boxFilterRef = useRef<HTMLInputElement>(null)
  const newBoxRef = useRef<HTMLInputElement>(null)
  const hintRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (openField === 'box') boxFilterRef.current?.focus()
    else if (openField === 'set') hintRef.current?.focus()
  }, [openField])

  /* WHAT THE BOX FILTER SHOWS. Substring on the box number — `9` keeps 9, 19, 95 and 99,
   * which is the mockup's own worked example — capped at nine rows BY CONSTRUCTION: digits
   * 1–9 are the only keys there are, so past nine the count says narrow again, and this
   * field can never out-grow the rarity list. With no filter the highest-numbered nine
   * stand in for "most recent": the store's boxes are allocated upward, recency is not a
   * fact `/status` carries, and the top of the range is the end the operator is working.
   * `boxMatchTotal` is the pre-cap count, so the meta can say `4 of 30 match` honestly
   * while only nine draw. */
  const boxMatchTotal = useMemo(() => {
    const query = boxFilter.trim()
    if (query === '') return boxes.length
    return boxes.filter((known) => String(known).includes(query)).length
  }, [boxes, boxFilter])

  const boxMatches = useMemo(() => {
    const query = boxFilter.trim()
    const all = query === '' ? boxes.slice(-9) : boxes.filter((known) => String(known).includes(query))
    return all.slice(0, 9)
  }, [boxes, boxFilter])

  /** One selection ends the opening: set the box, drop the note, close, and hand focus back
   *  so C and U are live again the moment a drawer is chosen. */
  const chooseBox = useCallback(
    (value: number) => {
      setBox(value)
      setBoxNote(null)
      closeField()
      blurActive()
    },
    [closeField],
  )

  /* The rarity list under its filter — same substring rule, case-insensitive because the
   * cells are Title Case and nobody narrows with a shift key. NOT capped at nine: the
   * vocabulary is fixed per game and all of it must stay claimable by mouse; what stops at
   * nine is the digit chips (see Opt), which one filter keystroke re-indexes. */
  const visibleRarities = useMemo(() => gameEntry?.rarities ?? [], [gameEntry])

  /* A DIGIT ACTS ONLY INSIDE AN OPEN FIELD, and always on what is currently VISIBLE — the
   * re-indexing rule. In the multi-select it toggles; in a single-select list or a track it
   * picks and closes; on the box list it picks the indexed match. Track cells draw no digit
   * chips (the mockup's call — four cells in 306px have no room for nine chips that would
   * mostly be blank) but the digits work there all the same, because "options ride digits"
   * is the design's one sentence about choosing and an exception per control shape is a
   * rule nobody can hold. A digit into a disabled cell does nothing, exactly like a click. */
  const fieldDigit = useCallback(
    (digit: number) => {
      if (digit < 1 || digit > 9) return
      const nth = digit - 1
      if (openField === 'rarity') {
        const name = visibleRarities[nth]
        if (name !== undefined) toggleRarity(name)
      } else if (openField === 'box') {
        const match = boxMatches[nth]
        if (match !== undefined) chooseBox(match)
      } else if (openField === 'game') {
        const entry = (registry?.games ?? [])[nth]
        if (entry !== undefined) {
          pickGame(entry.key)
          closeField()
        }
      } else if (openField === 'camera') {
        const device = camera.devices[nth]
        if (device !== undefined) camera.selectDevice(device.deviceId)
      } else if (openField === 'finish') {
        /* CELL ORDER IS THE GAME'S ENUM ORDER, FLAT — the "no claim" cell that used to sit
         * at position 1 is gone (owner's ruling, 2026-08-23), so digit N is the Nth finish
         * rather than the Nth-minus-one. This branch is the reason that ruling could not be
         * a render-only change: left as it was, `1` would have CLEARED the claim while
         * every other digit picked one finish too far along — silently, on the control the
         * operator uses at feeder pace, with the track drawing the right thing all the
         * while. The digits are the keyboard path this screen is built around, so a
         * one-cell change to the track is always a change here too. */
        const member = (gameEntry?.finishes ?? [])[nth]
        if (member === undefined) return
        if (offeredFinishes !== null && !offeredFinishes.has(member)) return
        // Re-pressing a claimed finish takes it back out, exactly as tapping its own cell
        // does — the toggle rule the removed "no claim" cell handed over to every cell, and
        // since D3's amendment the way to clear the whole claim as well.
        //
        // NO `closeField()` HERE ANY MORE, and it is a real cadence change rather than a
        // tidy-up: a multi-select cannot close on the first press or the second member
        // could never be claimed. The field now closes on Esc or F, which is one more key
        // on a screen that runs at a 623 ms feeder cadence — and it is the rarity field's
        // existing behaviour a few branches up, so the idiom is one the operator already
        // has rather than a second rule for one control.
        toggleFinish(member)
      } else if (openField === 'rotation') {
        const value = ROTATIONS[nth]
        if (value !== undefined) {
          camera.setRotation(value)
          closeField()
        }
      } else if (openField === 'trigger') {
        if (nth === 0) switchTrigger('manual')
        else if (nth === 1) switchTrigger('motion')
        else return
        closeField()
      }
    },
    [
      openField,
      visibleRarities,
      toggleRarity,
      boxMatches,
      chooseBox,
      registry,
      pickGame,
      closeField,
      camera,
      gameEntry,
      offeredFinishes,
      toggleFinish,
      switchTrigger,
    ],
  )

  /* THE FIELD KEYS, on the window in the bubble phase — after the `,` leader's
   * capture-phase listener (App.tsx), beside the two run keys the trigger seam owns.
   * `c` and `u` never appear in FIELD_KEYS, so this listener and the triggers cannot
   * contest a press; a key typed into any input is typing (isEditableTarget), except
   * Esc, which types nothing and must work from inside a filter or the open field
   * becomes a mouse-only trap. Modifier chords pass through untouched for App.tsx's
   * reason: Cmd-R is the browser's, and a shell that eats it broke something it does
   * not own. */
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return

      if (event.key === 'Escape') {
        if (openField !== null) {
          event.preventDefault()
          setOpenField(null)
          blurActive()
        }
        return
      }

      if (isEditableTarget(event.target)) return

      const key = event.key.toLowerCase()
      const field = FIELD_KEYS[key]
      if (field !== undefined) {
        // A letter for a field the chosen game does not draw is dead, not an error: `misc`
        // renders no Rarity or Finish row, and opening an empty picker would render a
        // control with nothing to pick — the not-loaded look this screen avoids by rule.
        if (field === 'rarity' && (gameEntry?.rarities.length ?? 0) === 0) return
        if (field === 'finish' && (gameEntry?.finishes.length ?? 0) === 0) return
        event.preventDefault()
        toggleField(field)
        return
      }

      if (openField === null) return

      if (key >= '1' && key <= '9') {
        event.preventDefault()
        fieldDigit(Number(key))
        return
      }

      // The new-box entry rides N, mirroring its drawn chip: reachable without a mouse
      // even though the filter holds focus on open.
      if (openField === 'box' && key === 'n') {
        event.preventDefault()
        newBoxRef.current?.focus()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [openField, gameEntry, toggleField, fieldDigit])

  /* What the video track actually negotiated — CameraPicker carried this readout and the
   * camera field inherits it whole, because it is the one number that makes the screen
   * honest: useCamera asks for 4K with a 720p floor, a constraint is a request, and showing
   * the result is how the owner finds out today's stream came up short BEFORE a box is shot
   * through it. `resize` on a video element is an intrinsic-dimension change — it fires when
   * the HDMI source switches mode mid-session, which a one-shot read at open would miss. */
  const [signal, setSignal] = useState<{ width: number; height: number } | null>(null)

  useEffect(() => {
    const video = camera.videoRef.current
    if (video === null) {
      setSignal(null)
      return
    }
    const read = () => {
      // Zero until the first frame decodes, and zero again after a teardown. Reporting
      // "0 x 0" as a resolution would be worse than reporting nothing.
      if (video.videoWidth === 0 || video.videoHeight === 0) {
        setSignal(null)
        return
      }
      setSignal({ width: video.videoWidth, height: video.videoHeight })
    }
    read()
    video.addEventListener('loadedmetadata', read)
    video.addEventListener('resize', read)
    return () => {
      video.removeEventListener('loadedmetadata', read)
      video.removeEventListener('resize', read)
    }
  }, [camera.videoRef, camera.deviceId, camera.ready])

  const underTarget = signal !== null && Math.max(signal.width, signal.height) < PIPELINE_LONG_EDGE

  const last = shots.length === 0 ? undefined : shots[shots.length - 1]

  /* THE RUN COUNTER, AND IT IS THE INSTRUMENT THAT ACTUALLY VERIFIES A CAPTURE.
   *
   * The Last capture panel's stated job is making a failed write visible, and at the feeder's
   * ~623ms — 5,778 cards an hour — nobody verifies anything by looking at a photograph. No
   * tethering product tries: Capture One owns a counter for exactly this, because the camera
   * cannot be asked how many frames it sent.
   *
   * What this repo already treats as proof is arithmetic, not an image. docs/GATES.md's Gate C
   * confirmation reads "85 records at indices 1..85, zero gaps, 85 distinct capture_ids" — and
   * that check has only ever been run afterwards, by hand, over the store. It is computed here
   * from `shots`, which is the same fact while the run is still going and while a gap can still
   * be re-fed.
   *
   * GAPS ARE COUNTED OVER THE SPAN, NOT AGAINST THE COUNT. A box whose run starts at index 41
   * has no gap; a run of 40 whose highest index is 45 has five. `next_index` is a high-water
   * mark (D10) so the span is what the allocator actually handed out.
   *
   * A REPLAYED capture_id IS NOT A SECOND CARD, which is why the distinct count is drawn beside
   * the total rather than instead of it: `created: false` means the server already had that id
   * and the photograph did not take a new position. Two numbers that differ is the one thing
   * on this screen that says a card may have passed the lens unrecorded. */
  const runCount = useMemo(() => {
    const mine = box === null ? [] : shots.filter((shot) => shot.card.box === box)
    if (mine.length === 0) return null
    const indices = mine.map((shot) => shot.card.index)
    const low = Math.min(...indices)
    const high = Math.max(...indices)
    const ids = new Set(mine.map((shot) => shot.card.capture_id ?? `none:${shot.card.key}`))
    return {
      shots: mine.length,
      low,
      high,
      gaps: high - low + 1 - new Set(indices).size,
      ids: ids.size,
    }
  }, [box, shots])

  const undoTarget = useMemo<UndoTarget | null>(() => {
    if (box === null) return null

    // The server's own newest for this box: the high-water mark, minus one. Zero for a box
    // it has never heard of, which is the same thing as empty for the comparison below.
    const serverNewest = nextForBox === undefined ? 0 : nextForBox - 1

    // Newest first, and only this box: the route deletes the newest card in the box it is
    // given, and repeated undo walks backwards one card per call.
    for (let i = shots.length - 1; i >= 0; i -= 1) {
      const shot = shots[i]
      if (shot !== undefined && shot.card.box === box) {
        /* THE SERVER WINS WHERE IT IS AHEAD. This session's shots carry a rendered label and
         * a thumbnail and `/status` carries neither, so a shot is the better thing to show —
         * but only while the two still agree about which card is newest.
         *
         * They stop agreeing in exactly two ways, and both are ordinary. A capture that
         * committed and lost its response (spec 5.5) is a card the server has and this list
         * does not; so is a capture the other device made into the same box, which D13
         * permits by design. In both cases the shot names a position that is no longer the
         * newest, and the route refuses anything but the newest — so nothing is destroyed,
         * but the control has shown the operator the wrong card and the press buys a
         * refusal. Spec 5.4 wants an undo you can aim, and aiming at a stale local guess is
         * the thing it is arguing against.
         */
        if (serverNewest > shot.card.index) break
        return { box: shot.card.box, index: shot.card.index, label: shot.card.label }
      }
    }
    if (serverNewest < 1) return null
    return { box, index: serverNewest, label: null }
  }, [box, nextForBox, shots])

  const doCapture = useCallback(async () => {
    if (busyRef.current) return
    // A halted run ignores the trigger entirely. Not "queues it": spec 5.5 rejected
    // queue-and-continue outright, because photos held in the browser and not yet on the Mac
    // are a second place inventory lives, and D13 has exactly one.
    // `gameEntry` rather than `game`, and it is not belt-and-braces: it is the guard that
    // makes the send below type-check without a non-null assertion, and it also refuses the
    // one state a bare `game !== null` would let through — a key the registry no longer
    // carries, after a server restart under a running session.
    if (halt !== null || box === null || !camera.ready || gameEntry === null) return
    // An unverified game cannot be captured at all (D22): no export exists, so the record
    // could never be joined. The server refuses it as `game_unverified` and this refuses it
    // one step earlier so the run is not halted by a refusal the screen could see coming.
    // NOT the same test as `catalogued` — see the message rendered under the Game field.
    if (gameEntry.unverified) return

    busyRef.current = true
    setBusy(true)
    try {
      let frame: string
      try {
        frame = await camera.grabFrameJpeg()
      } catch (err) {
        // A capture that produced no frame is a capture that produced no record. Same halt,
        // different remedy — the run stops either way.
        setHalt({ where: 'camera', ...describe(err) })
        return
      }

      // Trimmed once, so what is shown under the photo is exactly what was sent.
      const hint = setHint.trim() === '' ? undefined : setHint.trim()

      /* One id per PHOTOGRAPH, not one per request — that distinction is the whole guard.
       * Minted here rather than at the top of this function so that a camera fault on a
       * fresh card leaves no id lying in the ref; minted from the ref rather than fresh so
       * that the fire after a resume carries the id of the photograph that halted.
       *
       * A newly grabbed frame with a held id is correct and not a compromise: on a replay
       * the server ignores the image entirely and answers with the card it already
       * committed. That is what lets the halt message ask for the same card back at the
       * lens — whichever way the lost request went, one press resolves it.
       */
      const captureId = captureIdRef.current ?? newCaptureId()
      rememberCaptureId(captureId)

      try {
        const card = await capture({
          box,
          imageBase64: frame,
          // ALWAYS SENT, never omitted, unlike the two claims below it — D21 makes the game
          // required because nothing downstream can infer one. See the `game` state.
          game: gameEntry.key,
          setHint: hint,
          // Omitted when nothing has been claimed, so the sidecar records no `variant` and
          // D3's rungs 2 and 3 stay live for this card. See NO_CLAIM_LABEL. Byte-identical
          // to the rarity claim's rule on the next line, which is what D3 asked for when it
          // made the two claims one shape.
          variant: finish.length === 0 ? undefined : finish,
          // Same omission rule one claim over (D23): an empty claim sends no key, the
          // sidecar records nothing, and the ladder walks as if the field never existed.
          rarityClaim: rarityClaim.length === 0 ? undefined : rarityClaim,
          captureId,
        })
        // Answered, so the next photograph gets its own id. Cleared on a replay too: the
        // ambiguity that id existed to resolve is now resolved. Through `rememberCaptureId`,
        // so the stored copy goes with it — an id left in the store after the server has
        // answered would be resent by the next capture and would answer for the wrong card.
        rememberCaptureId(null)
        /* `created: false` means this id had already been committed — the halt before it
         * lost a response, not a card. The server returned the original position and burned
         * no index, which is only true because the id was held across the halt.
         *
         * Surfaced rather than swallowed, because the operator is holding a card and needs
         * to know whether it has a position. Cleared by the next capture that creates one. */
        setReplayed(card.created ? null : card.label)
        setShots((prev) =>
          // A replayed capture_id returns the original card with `created` false. Guarding on
          // the key rather than on `created` keeps that from appending a second entry for one
          // physical card, which would put a phantom position under the undo control.
          prev.some((shot) => shot.card.key === card.key)
            ? prev
            : [...prev, { card, setHint: hint ?? null, finish, game: gameEntry }],
        )
        setNextIndex((prev) => ({ ...prev, [String(card.box)]: card.index + 1 }))
        setRevision((prev) => prev + 1)
        setUndoNote(null)
      } catch (err) {
        // The id stays in the ref. This is the case it exists for: the request may have
        // committed, and only resending the same id can tell the difference without costing
        // a position.
        setHalt({ where: 'server', ...describe(err) })
      }
    } finally {
      busyRef.current = false
      setBusy(false)
    }
    // `rememberCaptureId` is stable (no dependencies of its own), so it is listed for
    // honesty rather than because it can change: an identity that moved per render would
    // re-arm the trigger seam, which keys its effect off `doCapture`.
  }, [box, camera, finish, gameEntry, halt, rarityClaim, rememberCaptureId, setHint])

  const doUndo = useCallback(async () => {
    if (busyRef.current || undoTarget === null) return
    // Read once into a local: `undoTarget` is derived from state this function is about to
    // change, so the value that named what would be deleted is the only value entitled to
    // say what was.
    const target = undoTarget
    busyRef.current = true
    setBusy(true)
    setUndoNote(null)
    try {
      /* The response is discarded on purpose. Its `deleted` is the store's own key — "3/7" —
       * and that is not a thing the operator has ever seen on this screen or anywhere else;
       * `types.ts` says as much where it defines the field ("Not a label and not a SKU").
       * What goes on screen is the rendered position that was under the control a moment
       * ago, which is the same string the server sent when the card was captured. */
      await undoCapture(target.box, target.index)
      setShots((prev) =>
        prev.filter((shot) => !(shot.card.box === target.box && shot.card.index === target.index)),
      )
      setNextIndex((prev) => ({ ...prev, [String(target.box)]: target.index }))
      setRevision((prev) => prev + 1)
      // Whatever the replay note said is about a card that may be the one just deleted, and
      // a stale sentence about a position that no longer exists is worse than none.
      setReplayed(null)
      // "Undo capture" produced "Undone" — docs/DESIGN.md's copy rule that an action keeps
      // its name through the flow.
      setUndoNote({ done: true, text: 'Undone', position: positionText(target), code: null })
    } catch (err) {
      // Deliberately not a halt. Spec 5.5 stops the run when a card may have gone past
      // unrecorded; a refused undo changed nothing at all, and the refusal names the position
      // that IS undoable. That is information beside the control, not a stopped run.
      setUndoNote({ done: false, position: null, ...describe(err) })
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }, [undoTarget])

  /* The seam, with both implementations behind it now. The key trigger is Gate B's; the
   * motion trigger is Gate C's, and the screen still does not know which one is armed —
   * it renders `captureTrigger.name` and fires whatever calls back. Undo is on the manual
   * primitive for its guards rather than for its future — auto-repeat, held modifiers and
   * keys typed into an input are all decided once, in one module, instead of in a second
   * window listener here that would have to be kept in step with it. Undo stays manual
   * forever: an automatic anything must never reach a control that hard-deletes. */
  const keyTrigger = useMemo(() => manualTrigger(CAPTURE_KEY), [])
  const machineTrigger = useMemo(
    // `camera.videoRef` is a stable ref object, so this is built once; each arm builds a
    // fresh machine, so counters restart when the mode is toggled — which reads correctly,
    // because toggling into motion is starting a run. The onFrame lambda reads the trace
    // through the ref, so a fresh recording per arm needs no re-memoisation.
    () =>
      motionTrigger(camera.videoRef, setMotionDiag, DEFAULT_PARAMS, (t, d, luma, event, cells) =>
        traceRef.current?.record(t, d, luma, event, cells),
      ),
    [camera.videoRef],
  )
  const captureTrigger = triggerMode === 'motion' ? machineTrigger : keyTrigger
  const undoTrigger = useMemo(() => manualTrigger(UNDO_KEY), [])

  /* Triggers arm once per identity and dispatch through a ref. Re-arming whenever the
   * closure changes would tear the motion machine down on every keystroke in the set hint
   * field and reset it mid-card — the exact failure the ref indirection was built against,
   * back when the machine was still hypothetical. A MODE CHANGE is the one legitimate
   * teardown moment, and it is exactly when `captureTrigger`'s identity changes, so the
   * effect's dependency does the right thing in both directions. */
  const fireCaptureRef = useRef<() => void>(() => {})
  const fireUndoRef = useRef<() => void>(() => {})
  useEffect(() => {
    fireCaptureRef.current = () => {
      /* In motion mode a declined fire is COUNTED, not just dropped. `doCapture` keeps its
       * own guards (they are the authority and other callers rely on them); this wrapper
       * reads the same conditions first so the drop leaves a number behind. Under a feeder
       * that keeps delivering, each of these is a card that may have passed the lens with
       * no record — spec 5.5's failure — and the halt banner below renders the `halted`
       * count as exactly that sentence. */
      if (triggerMode === 'motion') {
        /* `held` is the replay guard meeting the machine, and it MUST come before the
         * ordinary guards: while captureIdRef holds the id of a photograph the server may
         * already have committed, the next capture will be sent under THAT id — and on a
         * replay the server ignores the image entirely. A machine fire here would send
         * the NEXT card's frame under the halted card's id: the server answers with card
         * A's position, the screen says "already recorded", and card B passes the lens
         * with no record while the UI reports it handled. So resolving a held id is
         * human-only — the banner says to press the button — and the machine's fires are
         * counted against `held` until it clears. */
        const reason = busyRef.current
          ? ('busy' as const)
          : halt !== null
            ? ('halted' as const)
            : captureIdRef.current !== null
              ? ('held' as const)
              : box === null
                ? ('noBox' as const)
                : !camera.ready
                  ? ('notReady' as const)
                  : null
        if (reason !== null) {
          setSwallowed((prev) => ({ ...prev, [reason]: prev[reason] + 1 }))
          return
        }
      }
      void doCapture()
    }
  }, [box, camera.ready, doCapture, halt, triggerMode])
  useEffect(() => {
    fireUndoRef.current = () => void doUndo()
  }, [doUndo])
  useEffect(() => captureTrigger.start(() => fireCaptureRef.current()), [captureTrigger])
  useEffect(() => undoTrigger.start(() => fireUndoRef.current()), [undoTrigger])

  function onBoxSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    const draft = boxDraft.trim()
    // Digits first, value second. `Number` rather than `Number.parseInt` once the shape is
    // known: parseInt reads a prefix and discards the rest, which is exactly the silent
    // coercion BOX_DIGITS exists to refuse. isSafeInteger then catches a string of twenty
    // digits, which is well formed and still not a box.
    const value = BOX_DIGITS.test(draft) ? Number(draft) : Number.NaN
    if (!Number.isSafeInteger(value) || value < 1) {
      // A courtesy, not the authority: the server validates the box and answers
      // `box_invalid`. This just saves the round trip. It says what a box is rather than
      // what was wrong with the draft, because the two rejected shapes — '1e3' and '3.7' —
      // are both things a person would call a number.
      setBoxNote('A box is a whole number, 1 or higher. Type the digits only.')
      return
    }
    // No confirmation step (spec 5.2). The typed number becomes the current box; if it is
    // already in use it is simply selected. Choosing closes the field — one selection ends
    // the opening, the same rule every picker in the sidebar follows.
    setBoxDraft('')
    chooseBox(value)
  }

  /* THE NOTE, SAVED AGAINST THE LAST CAPTURE — the one write on this screen aimed at a card
   * other than the next one.
   *
   * WHY IT IS HERE AND NOT IN THE SIDEBAR WITH THE OTHER CLAIMS. Box, game, set hint and
   * finish are all things you set once and leave alone for a stack; a note is per card, and
   * a per-card text field placed BEFORE the shutter would put a keyboard on the critical
   * path of a run whose feeder emits every ~623 ms. So it is a correction applied after the
   * fact, through `PUT /inventory/<box>/<index>`, to a position that already exists — which
   * is also why nothing about capture waits for it and why an empty note is not an error.
   *
   * IT DOES NOT TOUCH `busy`. That flag gates the shutter and counts swallowed trigger
   * fires; blocking it while somebody types would drop feeder cards and report them as the
   * screen refusing a fire, which is spec 5.5's loudest failure and would be a lie here.
   *
   * The trimmed empty string is sent as `null` and not as `''`: that is how a note is
   * CLEARED, and `updateCard` keeps "absent" and "null" apart precisely so it can be. */
  const saveNote = useCallback(
    async (target: Shot, text: string) => {
      if (noteBusy) return
      setNoteBusy(true)
      setNoteSaved(null)
      const trimmed = text.trim()
      try {
        await updateCard(target.card.box, target.card.index, {
          note: trimmed === '' ? null : trimmed,
        })
        setNoteSaved({
          done: true,
          code: null,
          text:
            trimmed === ''
              ? `Note cleared on ${target.card.label}.`
              : `Note saved on ${target.card.label}.`,
        })
      } catch (err) {
        // NOT A HALT. A failed note leaves a card that is photographed, positioned and
        // recorded — everything a halt exists to protect. Stopping the run over a line of
        // text would cost cards to save prose.
        setNoteSaved({ done: false, ...describe(err) })
      } finally {
        setNoteBusy(false)
      }
    },
    [noteBusy],
  )

  /* A new capture is a new card, so the draft and its receipt belong to it and not to the
   * one before. Keyed on the position rather than on `last` itself: a re-render that rebuilt
   * the shot object would otherwise wipe a note being typed. */
  const lastKey = shots.length === 0 ? null : shots[shots.length - 1]?.card.key
  useEffect(() => {
    setNoteDraft('')
    setNoteSaved(null)
  }, [lastKey])

  const canCapture =
    halt === null &&
    !busy &&
    box !== null &&
    camera.ready &&
    gameEntry !== null &&
    !gameEntry.unverified

  /* HOW MANY FRAMES THERE ARE TO SAVE, from the recording itself.
   *
   * The Save control used to be rendered on `motionDiag !== null && motionDiag.frames > 0`,
   * and that was wrong twice over.
   *
   * The one that loses data: `switchTrigger` clears `motionDiag` and deliberately KEEPS the
   * trace — its comment says disarming leaves the old recording around "so it can still be
   * saved after the run stops" — but the control keyed off the diagnostics, so pressing
   * `key` made the button vanish and the next arm overwrote the recording. A feeder pass
   * ended the natural way, by disarming, could not be saved at all. That file is D19's
   * Tier-1 instrument and the whole reason the recording exists.
   *
   * The one that misreports: `motionDiag.frames` is the MACHINE's counter and it keeps
   * climbing past `MAX_FRAMES`, where the trace has marked itself truncated and stopped
   * growing. The label promised a file bigger than the file.
   *
   * Read off a ref during render, which is worth a sentence because it is normally a smell:
   * `traceRef` is written by the sampler ~30 times a second and nothing re-renders on its
   * account, so this is not a value React is tracking. It does not have to be. The only
   * moments the answer can change from "hidden" to "shown" or back are a diagnostics tick
   * and a mode change, and both are state updates that re-render on their own. */
  const traceFrames = traceRef.current?.frameCount ?? 0

  /* THE FRAMES ARE ALWAYS PORTRAIT NOW, because the rotation is always a quarter turn
   * (`useCamera.ts:ROTATIONS`, narrowed to 90/270 by the owner on 2026-08-24). The camera is
   * mounted on its side so a portrait card fills the portrait field, and the Cam Link hands
   * the browser a landscape frame regardless — so the preview turns with the stored photo and
   * the operator sees the card the way the pipeline will.
   *
   * Display only: the encode worker and the motion sampler both read the element's intrinsic
   * frames, which a CSS transform never touches.
   *
   * THE `turned` TERNARIES ARE GONE RATHER THAN LEFT ALWAYS-TRUE. They chose between a
   * portrait and a landscape stage, and the landscape half is now unreachable — TypeScript
   * said so, which is what a narrowed union is for. A branch that cannot be taken is a branch
   * a later reader has to prove cannot be taken. */
  const frameClass = 'capture-frame capture-frame-portrait'
  const stageClass = 'capture-stage capture-stage-portrait'
  const liveMediaClass = `capture-media capture-media-turn${camera.rotation}`

  /* Why the capture control is unavailable — first match wins, in the order the operator
   * can act on them.
   *
   * The camera's own faults are deliberately not in this list. `useCamera` reports a missing
   * remembered device and a stream error, the Camera field prints both verbatim — its rest
   * row says `fault` and the sentence is one keypress behind V — and spec 6.1's requirement
   * that the app say so and ask rather than fall back to another lens is met there.
   * Repeating either sentence here would put the same words on screen twice and give a
   * later edit two places to keep true. */
  const blocked =
    halt !== null
      ? // Above, not below: the halt renders before the stage, so the resume control is up
        // the page from this line in both the two-column and the stacked layout. Pointing
        // the operator the wrong way costs the seconds a stopped run has least of, and
        // docs/DESIGN.md's copy rules ask an error to say what to do next — which includes
        // being right about where.
        'Captures are paused. Resume them above.'
      : gameEntry === null
        ? // NOT "pick a game" — there is nothing to pick from yet, and telling the operator
          // to do something the screen cannot offer is worse than saying nothing. Which of
          // the two sentences depends on whether the fetch failed or is simply outstanding.
          registryNote === null
          ? 'Waiting for the game list from the server.'
          : 'The game list did not load, so there is nothing to capture as. Ask again in the sidebar.'
        : gameEntry.unverified
          ? // D22's refusal, in the operator's terms rather than the server's. It names the
            // game, says what is missing, and says what would fix it — docs/DESIGN.md's copy
            // rule. Owner-side, so naming the file is allowed and is the useful part.
            `${gameEntry.display} has no TCGplayer export yet, so a card captured as one could ` +
            'never be identified, priced or listed. Pick another game, or add its export and ' +
            'author its rarities in pipeline/games.py first.'
          : box === null
            ? 'Pick a box, or type a new one, before capturing.'
            : !camera.started
              ? // A FOURTH CASE, since 2026-08-23: the camera no longer opens on mount, so
                // "no camera" is now three states and not one. `started` false is nobody has
                // asked — an ordinary beginning to a session, not a fault — and it is the
                // only one of the three that belongs here. `missing` and `error` stay out
                // for the reason above: CameraPicker prints both, verbatim, a few pixels up.
                'Open the camera in the sidebar before capturing.'
              : null

  return (
    /* TWO COLUMNS: the controls beside the frames instead of above and below them.
     *
     * The owner asked for a screen where "everything shows at 100% on my browser tab, no
     * scrolling", and said the undo "can clearly be on the side too". Stacked, this screen
     * spent ~1150px of height inside a 900px window while leaving a third of the width
     * empty — a bar of controls, two frames, and a full-width undo strip, in that order.
     *
     * So: every control in one sidebar column, the two frames in the other, and the frame
     * height derived from the space actually left over rather than from a constant that was
     * right on one window. The stylesheet does that arithmetic; see --portrait-h.
     *
     * Nothing here tells the stylesheet whether a halt is showing, and an earlier draft that
     * did — a `capture-halted` class carrying a reserved height for the banner — is worth
     * knowing about because it is the obvious thing to reach for. It reserved 390px; a halt
     * in motion mode with a swallowed-fire count measures 433.5, and the difference was a
     * scrolling page. The banner sizes itself and the frames take what is left.
     */
    <main className="capture">
      {/* FULL WIDTH AND FIRST, above both columns. It was above the stage before and it is
          above everything now, which is what keeps `blocked`'s "Resume them above" true
          when read from the sidebar as well as from the stage. */}
      {halt === null ? null : (
        <section className="capture-halt" role="alert">
          <h2 className="capture-halt-title">
            {halt.where === 'camera'
              ? 'Captures are paused. No frame came from the camera.'
              : 'Captures are paused. The card was not recorded.'}
          </h2>
          {/* The server's own message, unchanged (spec section 4). */}
          <p className="capture-halt-message">{halt.text}</p>
          {/* What to do next, which docs/DESIGN.md's copy rules require of an error and which
              the server cannot know. "May not have been recorded" rather than "was not":
              a request can commit and lose its response, and claiming certainty either way
              is how one physical card ends up with two positions or none.

              The server line asks for the same card back rather than for it to be set aside,
              and that instruction is only honest because the capture id is now held across
              the halt. One press then settles it both ways: if the request never committed
              the card is recorded normally, and if it did the server replays the original
              position and burns no index. Set the card aside instead and the run continues
              with the ambiguity unresolved, which is the state D10's positions cannot
              survive. */}
          <p className="capture-halt-message">
            {halt.where === 'camera'
              ? 'Set aside the card at the lens and check the camera feed before you resume.'
              : 'Leave the card at the lens and capture it again after you resume. It may ' +
                'already have been recorded, and the app will say so rather than give it a ' +
                'second position.'}
          </p>
          <p className="capture-halt-message">
            {last === undefined ? (
              'Nothing has been recorded in this session.'
            ) : (
              <>
                The last card recorded is{' '}
                <span className="capture-inline-label">{last.card.label}</span>.
              </>
            )}
          </p>
          {/* Human sentence large, machine string small — the reason-code pattern from
              docs/DESIGN.md, owner-side, so what you saw on screen is greppable across the
              app and the server log. */}
          {halt.code === null ? null : <p className="capture-halt-code">{halt.code}</p>}
          {/* Spec 5.5's sentence, for the one situation where a halt is not enough on its
              own: a machine trigger with a feeder still delivering. Each of these fires is
              a card the trigger saw and the screen refused, and physically it may be in
              the box by now with no photo and no position. The count is what turns "the
              run was paused for a bit" into "go check the last N cards", which is the
              difference between a pause and a loss. */}
          {triggerMode === 'motion' && swallowed.halted > 0 ? (
            <p className="capture-halt-message">
              The motion trigger fired{' '}
              <span className="capture-inline-label">{swallowed.halted}</span>{' '}
              {swallowed.halted === 1 ? 'time' : 'times'} while captures were paused. If the
              feeder kept moving, that many cards may have passed the lens unrecorded — set
              them aside and re-feed them after you resume.
            </p>
          ) : null}
          {triggerMode === 'motion' && halt.where === 'server' ? (
            <p className="capture-halt-message">
              After you resume, capture the held card with the button yourself. The machine
              will not re-present a card it has already fired on, and the paused
              photograph's id must go back with the same card — not with whatever the
              feeder delivers next.
            </p>
          ) : null}
          {/* The fill moves here while the run is stopped: the capture control renders
              disabled, so there is again exactly one thing to do, which is what
              docs/DESIGN.md reserves the solid accent for. No key hint — an explicit
              acknowledgement is the point, and a key would let muscle memory resume a run
              the operator has not read the message on. */}
          <PullConfirm
            label="Resume captures"
            onConfirm={() => {
              setHalt(null)
              /* This pause's swallowed-fire count has been read and acted on — the banner
               * told the operator how many cards to set aside. Carrying it into the next
               * pause would tell them to re-feed cards they already re-fed. */
              setSwallowed((prev) => ({ ...prev, halted: 0 }))
              /* Ask the server where the box actually is. The local high-water mark is a
               * guess from the moment a capture fails: the request may have committed and
               * lost its response, in which case this box's next index moved and nothing on
               * this side saw it — and undo would then aim one card too early. Nothing else
               * in the screen refetches `/status`, by design (a round trip per card at a rig
               * firing every few seconds buys nothing), so this resume is the one moment the
               * stale number can be corrected without a reload.
               *
               * Run on both kinds of halt rather than only the server one. A camera fault
               * sent no request, but a stopped run is also a window in which the other
               * device (D13) can capture into the same box — and one path is easier to keep
               * true than two conditioned on a distinction that does not change the answer.
               */
              void loadStatus()
            }}
          />
        </section>
      )}

      {/* A CAPTURE THAT OUTLIVED THE PAGE (D27), and it is up here with the halt rather than
          beside the shutter for two reasons that point the same way.

          It changes what the next press MEANS, so it has to be read before the next press.
          The id of a photograph the server never answered for came back from
          `sessionStorage`; the halt that produced it did not, because a halt is this screen's
          reaction to one failed request and its text is the server's own, which spec section
          4 forbids paraphrasing and this could only have invented. So this says the one thing
          that banner would have said: put the SAME card back. On a replay the server ignores
          the image entirely and answers with the card it already committed — so a press with
          the next card at the lens answers for the held one and lets the new one past with no
          record at all. Restoring the id silently would trade an unresolvable ambiguity for a
          quiet one.

          And the height budget absorbs it here. Above the shell it takes its room from the
          frames, exactly as the halt does; in the sidebar it would have pushed a column that
          fits by ~15px into scrolling the page.

          NOT RENDERED UNDER A HALT, because the halt already says it in the server's own
          terms and says it louder. Two banners about one card is one banner too many.

          No dismiss control, deliberately: dismissing it is precisely what a reload used to
          do. One press with the right card settles it in both directions, and closing the tab
          ends the session store with it. */}
      {halt !== null || !heldAcrossReload ? null : (
        <section className="capture-carried" role="status">
          <p className="capture-halt-message">
            A capture from before this page reloaded was never confirmed. Put that same card
            back at the lens and capture it — if the server did record it, it will say so and
            give it no second position. Do not feed the next card first.
          </p>
        </section>
      )}

      <div className="capture-shell">
        {/* THE CONTROL SIDEBAR — pass D, and its one structural idea is the CADENCE SPLIT.
            Box, Set hint, Rarity and Finish are the per-stack CLAIMS and get the panel's
            top; Game, Camera, Rotation and Trigger are set once a session and collapse to
            a quiet footer group below the actions. The bet that split makes is named in
            the mockup and carried here: a mid-session rotation fix now lives in a 24px
            footer row. The mockup's own `Capture` brand head is NOT reproduced — the app
            nav sits 46px above this column already saying which screen this is, and a
            duplicate title is 36px of the exact "oversized boxes" complaint this pass
            exists to answer. */}
        <aside className="capture-side">
          <div className="capture-side-fields">
            {/* BOX FIRST among the claims — it is the one with a physical drawer under it.
                The game moved to the session group below the actions: it decides what the
                other pickers may offer, but it is decided once per session, and the fields
                it governs simply do not render until the registry lands. */}
            {openField === 'box' ? (
              <OpenField
                k="B"
                label="Box"
                meta={
                  box === null
                    ? `no box · ${boxes.length} ${boxes.length === 1 ? 'box' : 'boxes'}`
                    : `Box ${box} · ${boxes.length} ${boxes.length === 1 ? 'box' : 'boxes'}`
                }
                onClose={closeField}
              >
                {/* THE FILTER, NEVER A LIST: thirty boxes cost what three cost, because
                    nothing ever draws more than nine rows and one typed digit re-narrows.
                    Substring match, so `9` keeps 19 and 95 as well as 9 — a box number is
                    remembered by its digits, not by its prefix. */}
                {boxes.length === 0 ? (
                  <p className="capture-quiet">No box holds a card yet. Type a number.</p>
                ) : (
                  <>
                    <div className="capture-entry">
                      <span />
                      <div className="capture-entrybox">
                        <input
                          ref={boxFilterRef}
                          className="capture-filter"
                          type="text"
                          inputMode="numeric"
                          aria-label="Narrow the box list"
                          placeholder="narrow, then Enter"
                          value={boxFilter}
                          onChange={(event) =>
                            setBoxFilter(event.target.value.replace(/[^0-9]/g, ''))
                          }
                          onKeyDown={(event) => {
                            // Enter takes a LONE match and only a lone match: with two or
                            // more left it does nothing, and the count beside the caret
                            // says why. A digit is always filter text here — box names ARE
                            // digits — so row selection under a focused filter is Enter,
                            // a click, or the digit keys once focus is elsewhere.
                            if (event.key !== 'Enter') return
                            event.preventDefault()
                            const lone = boxMatchTotal === 1 ? boxMatches[0] : undefined
                            if (lone !== undefined) chooseBox(lone)
                          }}
                        />
                        <span className="capture-entrymeta">
                          {boxFilter.trim() === ''
                            ? `${boxes.length} in use`
                            : `${boxMatchTotal} of ${boxes.length} match`}
                        </span>
                      </div>
                    </div>
                    <div className="capture-opts">
                      {boxMatches.map((known, position) => (
                        <Opt
                          key={known}
                          k={String(position + 1)}
                          on={known === box}
                          name={`Box ${known}`}
                          // Verbatim from GET /status. Not a card count — it is a
                          // high-water mark, and the two disagree once a record is removed.
                          trail={`next ${nextIndex[String(known)] ?? '?'}`}
                          onPick={() => chooseBox(known)}
                        />
                      ))}
                    </div>
                  </>
                )}
                {/* The new-box entry keeps every rule its old form had: digits only, no
                    confirmation step (spec 5.2 — the owner declined one), the typed number
                    simply becomes the current box. Enter submits the one-input form. */}
                <form
                  className="capture-entry"
                  onSubmit={(event) => {
                    onBoxSubmit(event)
                  }}
                >
                  <span className="capture-k">N</span>
                  <input
                    ref={newBoxRef}
                    className="capture-filter"
                    type="number"
                    min="1"
                    step="1"
                    inputMode="numeric"
                    placeholder="new box number"
                    aria-label="Start a new box"
                    value={boxDraft}
                    onChange={(event) => {
                      setBoxDraft(event.target.value)
                      setBoxNote(null)
                    }}
                  />
                </form>
                <p className="capture-opennote">
                  Digits narrow and re-index; Enter takes a lone match. Enter on N adds the
                  box and switches to it.
                </p>
                {boxNote === null ? null : <p className="capture-quiet">{boxNote}</p>}
              </OpenField>
            ) : (
              <Row
                k="B"
                label="Box"
                right={
                  box === null ? (
                    <span className="capture-val is-default">none</span>
                  ) : (
                    <span className="capture-val">
                      {box}
                      {/* `empty` earns the sub when the high-water mark says the drawer
                          holds nothing yet — the earlier of the two chances to catch a
                          typed 33 for 3, kept from the old flag. Otherwise the sub is the
                          server's own next index, the same fact the option rows trail. */}
                      <em className="capture-sub">
                        {boxIsEmpty ? 'empty' : `next ${nextForBox ?? '?'}`}
                      </em>
                    </span>
                  )
                }
                onToggle={() => toggleField('box')}
              />
            )}

            {/* Free text, not a picker: there is no catalog in the repo until build-order
                step 9, so a picker has no list to offer. Optional, and worth the field —
                without it a collector number that matches rows in two sets reviews as
                `set_ambiguous`. */}
            {openField === 'set' ? (
              <OpenField k="S" label="Set hint" meta="optional" onClose={closeField}>
                <form
                  className="capture-entry"
                  onSubmit={(event) => {
                    event.preventDefault()
                    closeField()
                    blurActive()
                  }}
                >
                  <span />
                  <input
                    ref={hintRef}
                    className="capture-filter"
                    type="text"
                    placeholder="sv09"
                    aria-label="Set hint"
                    value={setHint}
                    onChange={(event) => setSetHint(event.target.value)}
                  />
                </form>
              </OpenField>
            ) : (
              <Row
                k="S"
                label="Set hint"
                right={
                  setHint.trim() === '' ? (
                    <span className="capture-val is-default">none</span>
                  ) : (
                    <span className="capture-val">{setHint.trim()}</span>
                  )
                }
                onToggle={() => toggleField('set')}
              />
            )}

            {/* RARITY AT REST IS THE BITFIELD: one 6px mark per rarity of the chosen game,
                catalog stack order, filled where claimed — the same positions at the same
                width every time you look, because width moves only when the game does and
                the game is a session setting. It says HOW MANY and AT WHICH POSITIONS,
                never WHICH NAMES: names live one keypress away behind R, and that trade is
                the mockup's, accepted with it.

                FEWER THAN TWO RARITIES DRAWS NO FIELD — the same threshold the finish row
                takes, moved here on the owner's ruling of 2026-08-23 for the same reason
                and in the same breath. `misc` authors none, and `pokemon_code` authors
                exactly one (`Code Card`), which made a multi-select offering a single
                option: a control whose only choice is whether to restate the one fact it
                could possibly carry. Both of the claim's jobs (D23) are degenerate there —
                a cross-check against one candidate rarity contradicts nothing, and
                narrowing the finish chips is moot for a game with one finish that now
                draws no chips either. Claiming nothing and letting the ladder read the
                catalog is the same answer by the honest route. */}
            {gameEntry !== null && gameEntry.rarities.length > 1 ? (
              openField === 'rarity' ? (
                <OpenField
                  k="R"
                  label="Rarity"
                  meta={`Choose any · ${rarityClaim.length} of ${gameEntry.rarities.length}`}
                  onClose={closeField}
                >
                  {/* NO FILTER BAR HERE, on the owner's ruling of 2026-08-23: "there's
                      not that many that i have to search for them." The longest list any
                      game authors is Pokemon's thirteen, and nine of those ride digits —
                      so the box the filter saved was never more than a few taps, while it
                      cost a focused input on every open of this field and a re-indexing
                      rule the operator had to hold in their head to read the digit chips.

                      The box filter is NOT the mirror case and deliberately keeps its own:
                      boxes are unbounded and already number in the nineties, which is the
                      condition this list can never reach — `rarities` is authored per game
                      in `pipeline/games.py` and grows only when a real catalog does. */}
                  {/* ANY NUMBER of marks is a legal claim, including none: toggling the
                      last one off IS the clear, the empty claim narrows nothing (D23), and
                      no separate reset control exists to learn. */}
                  <div className="capture-opts">
                    {visibleRarities.map((name, position) => {
                      const [stem, sfx] = rarityNameParts(name)
                      return (
                        <Opt
                          key={name}
                          k={position < 9 ? String(position + 1) : undefined}
                          on={rarityClaim.includes(name)}
                          name={stem}
                          sfx={sfx}
                          onPick={() => toggleRarity(name)}
                        />
                      )
                    })}
                  </div>
                </OpenField>
              ) : (
                <Row
                  k="R"
                  label="Rarity"
                  right={
                    <span
                      className="capture-bits"
                      role="img"
                      aria-label={`${rarityClaim.length} of ${gameEntry.rarities.length} claimed`}
                    >
                      {gameEntry.rarities.map((name) => (
                        <span
                          key={name}
                          className={rarityClaim.includes(name) ? 'capture-bit on' : 'capture-bit'}
                        />
                      ))}
                    </span>
                  }
                  onToggle={() => toggleField('rarity')}
                />
              )
            ) : null}

            {/* A GAME WITH FEWER THAN TWO FINISHES DRAWS NO FIELD, and the threshold moved
                from zero to one on the owner's ruling of 2026-08-23. The zero case was
                always here: `misc` declares an empty vocabulary — a Yu-Gi-Oh or Weiss card
                has no finish this pipeline knows how to claim — and a Finish row offering
                only "no claim" is a control with nothing to pick, which reads as something
                failing to load rather than as nothing to say.

                THE ONE-FINISH CASE IS THAT SAME SENTENCE ONE STEP ALONG. `pokemon_code`
                stocks `normal` and nothing else, so its Finish row offered "no claim" beside
                a single cell — two cells, one real choice, and the owner named it as making
                no sense. It does not.

                DRAWN AS ABSENT RATHER THAN AS AUTO-SELECTED, WHICH IS THE PART D23 DECIDES.
                The owner's first instinct was that a lone finish "would always be selected",
                and D23 refuses exactly that: an auto-selected claim is a MANUFACTURED one,
                and D3 rung 1 outranks rung 2, so claiming `normal` on the operator's behalf
                would make `CATALOG_FORCED` unreachable for every card of that game. Not
                drawing the control claims nothing, leaves rung 2 to resolve the only finish
                the catalog stocks, and reaches the same record by the honest route. Ruled
                that way by the owner on 2026-08-23; D23 is not reopened.

                A finish claimed under a game that DOES draw the field must not survive a
                switch to one that does not — see the clearing effect above, which drops it
                on this same threshold. Otherwise a claim would ride along on a control the
                operator cannot see, let alone take back. */}
            {gameEntry !== null && gameEntry.finishes.length > 1 ? (
              openField === 'finish' ? (
                <OpenField
                  k="F"
                  label="Finish"
                  meta={`Choose any · ${finish.length} of ${gameEntry.finishes.length}`}
                  onClose={closeField}
                >
                  {/* The pipeline's own strings, verbatim, cell for cell — the same
                      no-second-vocabulary rule the chips followed (see NO_CLAIM_LABEL).
                      An excluded cell stays drawn and refuses, so the operator can see
                      what the rarity claim cost; the sentence below the track is where
                      `not stocked` is said at full contrast.

                      THERE IS NO "no claim" CELL, on the owner's ruling of the same day:
                      nothing selected IS no claim, and a cell for it is a choice that only
                      restates the absence of the others. Clearing is re-tapping the cell
                      that is on — which is the idiom the rarity claim beside it already
                      uses, and which `Track` was already marked up for: its cells carry
                      `aria-pressed`, so they have always been toggles rather than radios.
                      The collapsed Row below still SAYS `no claim` at full contrast, so the
                      state stays named where it is read; what went is the cell that made
                      naming it a thing to pick. */}
                  <Track
                    label="Finish"
                    cells={gameEntry.finishes.map((member) => ({
                      text: member,
                      on: finish.includes(member),
                      disabled: offeredFinishes !== null && !offeredFinishes.has(member),
                      // MULTI-SELECT SINCE D3's AMENDMENT (2026-08-23), and `Track` needed
                      // no change for it: its cells have always carried `aria-pressed` and
                      // the stylesheet keys on `[aria-pressed='true']` per cell, so several
                      // can read as on already. It stays shared with the rotation and
                      // trigger tracks, which are still single-select — the component was
                      // never the thing enforcing that.
                      //
                      // It does NOT close on pick: a set is built by more than one press.
                      onPick: () => toggleFinish(member),
                    }))}
                  />
                  {offeredFinishes === null ||
                  gameEntry.finishes.every((member) => offeredFinishes.has(member)) ? null : (
                    <p className="capture-opennote">
                      {gameEntry.finishes
                        .filter((member) => !offeredFinishes.has(member))
                        .join(' · ')}{' '}
                      — not stocked under the claimed rarities
                    </p>
                  )}
                </OpenField>
              ) : (
                <Row
                  k="F"
                  label="Finish"
                  /* THE PIPELINE'S OWN STRINGS, joined — not the rarity row's bitfield,
                     and the difference is deliberate. That row draws a bitfield because
                     Pokemon authors thirteen rarities and they cannot be spelled out; a
                     game authors at most three finishes. Spelling them keeps NO_CLAIM_LABEL
                     readable AT FULL CONTRAST in the same slot, which is the property the
                     removed "no claim" cell handed to this row and which a bitfield says
                     only in an aria-label.

                     THE COST, recorded rather than designed around: `.capture-val` is
                     nowrap + ellipsis at 12px, so all three of Pokemon's finishes claimed
                     at once truncates. One and two members fit. The full claim is one
                     keypress away in the open field and the last-capture panel shows what
                     was actually sent, so the failure is a shortened label rather than a
                     wrong one — but if a real session claims all three often, the bitfield
                     is the fix to reach for. */
                  right={
                    finish.length === 0 ? (
                      <span className="capture-val is-default">{NO_CLAIM_LABEL}</span>
                    ) : (
                      <span className="capture-val">{finish.join(' · ')}</span>
                    )
                  }
                  onToggle={() => toggleField('finish')}
                />
              )
            ) : null}

            {statusNote === null ? null : (
              <div className="capture-servernote">
                <p className="capture-quiet">{statusNote.text}</p>
                <button type="button" className="capture-go" onClick={() => void loadStatus()}>
                  Ask again
                </button>
              </div>
            )}
          </div>

          {/* THE FOOT: the two controls that must never scroll out of reach.
              Everything above is a setting, chosen at the top of a run and then left alone,
              so it is what gives up room on a short window. These two are the run itself —
              the shutter, and the one control in the app that hard-deletes. A capture button
              you have to scroll a column to find is a card photographed late or not at all,
              and an undo you have to go looking for is reached for after the next card has
              already gone past. */}
          <div className="capture-side-foot">
            <div className="capture-controls">
              <PullConfirm
                label="Capture card"
                onConfirm={() => void doCapture()}
                disabled={!canCapture}
                // In motion mode the C key is genuinely disarmed — the seam holds one trigger
                // at a time — so advertising it would be a chip for a key that does nothing.
                // The button itself stays live in both modes: a manual fire past a hesitant
                // machine is an override, not a mode.
                keyHint={triggerMode === 'manual' ? CAPTURE_KEY_LABEL : undefined}
              />
              {/* Which trigger is armed — the line trigger.ts promised would answer this
                  question — is no longer here. It read as debug output under the shutter;
                  it is the Trigger field's own machine string now, beside the control it
                  describes. Same class, same text, one field up the column. */}

              {/* The machine's own vitals, only while it is the armed trigger. `d` is the
                  live frame-difference every threshold in motion.ts is set against, on
                  screen so the rig session TUNES against a number it can see: an empty
                  still scene should read well under 1, a card swap should spike past 6.
                  Mono, uppercase-free machine words — this is metadata, owner-side. */}
              {triggerMode !== 'motion' ? null : motionDiag === null ? (
                <p className="capture-quiet">
                  Motion is armed but no frame has reached it yet. Open a camera and the
                  readout appears here.
                </p>
              ) : (
                <p className="capture-motion-hud">
                  <span>{motionDiag.phase}</span>
                  <span>d {motionDiag.d.toFixed(2)}</span>
                  <span>luma {Math.round(motionDiag.luma)}</span>
                  <span>fires {motionDiag.fires}</span>
                  <span>same {motionDiag.suppressedUnchanged}</span>
                  <span>empty {motionDiag.suppressedNoCard}</span>
                  <span>stall {motionDiag.stalled}</span>
                  {swallowed.busy + swallowed.noBox + swallowed.notReady + swallowed.held ===
                  0 ? null : (
                    <span className="capture-refused">
                      dropped{' '}
                      {swallowed.busy + swallowed.noBox + swallowed.notReady + swallowed.held}
                    </span>
                  )}
                </p>
              )}
              {/* D19's Tier-1 instrument, one press: the whole armed session's timing signal
                  plus the exact watch-region pixels each gate decided on, as a JSON download.
                  One feeder pass with this file is the tuning data — period, jitter, how
                  long a card is moving versus still — measured instead of derived, and
                  re-scorable offline against different thresholds without another rig trip.
                  Rendered only when there is something to save; the recording itself costs
                  nothing the HUD was not already paying. */}
              {traceFrames > 0 ? (
                <button
                  type="button"
                  className="capture-go"
                  onClick={() => traceRef.current?.download()}
                >
                  Save trace · {traceFrames} frames
                </button>
              ) : null}
              {blocked === null ? null : <p className="capture-quiet">{blocked}</p>}
              {/* The one thing the retry guard is for, said out loud. It appears only after a
                  resume, and it is the answer to the question the halt could not settle: the
                  paused capture did reach the server, so this photograph took no new position.
                  Beside the capture control rather than in the panel opposite, because that is
                  where the operator is looking at the moment they press again. */}
              {replayed === null ? null : (
                <p className="capture-quiet">
                  Already recorded at{' '}
                  <span className="capture-inline-label">{replayed}</span>. The paused capture
                  did reach the server, so nothing new was recorded and no position was used.
                  Move on to the next card.
                </p>
              )}
            </div>

            {/* Always visible, never appearing after a capture: a control that appears and
                disappears is one you have to look for at the moment you are least inclined
                to. It was a full-width strip under the frames until the owner said it "can
                clearly be on the side too", and that strip was ~90px of the height this
                layout needed back. */}
            <footer className="capture-undo">
              <div className="capture-undo-target">
                {undoTarget === null ? (
                  <p className="capture-quiet">Nothing in this box to undo.</p>
                ) : (
                  <>
                    {/* Empty alt on purpose, not by omission: the position beside it is the same
                        fact in words, and what the thumbnail adds — whether this is the card you
                        meant — is not a thing alt text can carry. */}
                    <img
                      className="capture-undo-thumb capture-undo-thumb-portrait"
                      src={photoSrc(undoTarget.box, undoTarget.index, revision)}
                      alt=""
                    />
                    <div>
                      <p className="capture-field-name">Undo deletes</p>
                      <p className="capture-label">{positionText(undoTarget)}</p>
                    </div>
                  </>
                )}
              </div>
              <div className="capture-undo-action">
                {/* No dialog, one tap, repeating (spec 5.4). The deleted photo is of a card still
                    in your hand, so the remedy for a wrong undo is to photograph it again — which
                    is why this is the stated exception to the no-confirm rule rather than a
                    violation of it. Allowed while the run is halted: the halt is about capturing,
                    and correcting the last good card is exactly what a stopped run is for. */}
                <button
                  type="button"
                  className="capture-undo-go"
                  onClick={() => void doUndo()}
                  disabled={undoTarget === null || busy}
                >
                  Undo capture <kbd className="capture-key">{UNDO_KEY_LABEL}</kbd>
                </button>
                {undoNote === null ? null : (
                  <p className={undoNote.done ? 'capture-quiet' : 'capture-refused'}>
                    {undoNote.text}
                    {/* The position in the utility face, inline in a body sentence — the same
                        string the server rendered when the card was captured. This used to say
                        "Undone 3/7": the store's own key, in the body face, naming a thing the
                        operator has never seen on any screen. */}
                    {undoNote.position === null ? null : (
                      <>
                        {' '}
                        <span className="capture-inline-label">{undoNote.position}</span>
                      </>
                    )}
                    {undoNote.code === null ? null : (
                      <span className="capture-halt-code"> {undoNote.code}</span>
                    )}
                  </p>
                )}
              </div>
            </footer>
          </div>

          {/* THE SESSION GROUP, below the actions and quieter — 24px rows to the claims'
              32, smaller type, one group caption. These four are set once when the rig is
              set up and then read, not touched: which game the stacks are, which lens the
              photos come through, which way the sensor is mounted, what fires the shutter.
              Putting them under the shutter is the cadence bet named at the top of the
              sidebar; what it buys is that the four rows the operator's eyes cross per
              stack are all claims. */}
          <div className="capture-session">
            <p className="capture-groupcap">Session</p>

            {/* THE RUN COUNTER. Not a claim and not a control — the one row in this sidebar
                that is evidence, which is why it sits at the top of Session rather than among
                the claims above. It answers the question the Last capture panel is asked to
                answer by eye and cannot at feeder pace: did every card that went past the lens
                get a position of its own?

                Drawn only once this box has a shot in this session, because before that there
                is nothing to count and a row of zeroes reads as a fault. */}
            {runCount === null ? null : (
              <p className="capture-runcount">
                <span className="capture-runcount-n">{runCount.shots}</span>
                <span className="capture-runcount-word">
                  captured &middot; #{runCount.low}&ndash;{runCount.high}
                </span>
                <span
                  className={
                    runCount.gaps === 0 && runCount.ids === runCount.shots
                      ? 'capture-runcount-ok'
                      : 'capture-runcount-off'
                  }
                >
                  {runCount.gaps === 0 ? 'no gaps' : `${runCount.gaps} missing`}
                  {' · '}
                  {runCount.ids === runCount.shots
                    ? `${runCount.ids} ids`
                    : `${runCount.ids} ids of ${runCount.shots}`}
                </span>
              </p>
            )}

            {/* The game decides what the claim fields above may offer — the finish enum
                and the rarity vocabulary are both per-game — and it still does: picking
                one here re-renders them and clears both claims (see pickGame). What moved
                is only WHERE it is decided, because D21 makes it a per-card claim that in
                practice changes once per session, not once per stack. */}
            {openField === 'game' ? (
              <OpenField k="G" label="Game" meta="Choose one" onClose={closeField}>
                <div className="capture-opts">
                  {(registry?.games ?? []).map((entry, position) => (
                    <Opt
                      key={entry.key}
                      k={position < 9 ? String(position + 1) : undefined}
                      on={entry.key === game}
                      name={entry.display}
                      /* The machine string, small, beside the human name — the reason-code
                         pattern docs/DESIGN.md sets for owner-side screens, so what is on
                         screen is greppable against `pipeline/games.py` and a run report. */
                      trail={entry.key}
                      onPick={() => {
                        pickGame(entry.key)
                        closeField()
                      }}
                    />
                  ))}
                  {registry === null ? (
                    <p className="capture-quiet">The server has not sent the game list yet.</p>
                  ) : null}
                </div>
                {registryNote === null ? null : (
                  <>
                    <p className="capture-quiet">{registryNote.text}</p>
                    <button type="button" className="capture-go" onClick={() => void loadGames()}>
                      Ask again
                    </button>
                  </>
                )}
                {/* THREE STATES, THREE DIFFERENT SENTENCES, AND NONE OF THEM IS THE OTHERS.
                    Collapsing any two would be the mistake this block exists to avoid:
                    `misc` is a settled, correct, permanent answer and must never render as
                    a fault, while `unverified` is a fault with a fix and has to say so.
                    Nothing renders for the ordinary case — a game that is catalogued,
                    verified and has a prompt says nothing, because a line of reassurance
                    on every capture is noise on the screen the owner spends hours in. The
                    sentences live inside the disclosure now; the one that blocks capture
                    (`unverified`) is also said at full length under the shutter, where
                    `blocked` has always said it. */}
                {gameEntry === null ? null : gameEntry.unverified ? (
                  <p className="capture-quiet">
                    No TCGplayer export has been seen for {gameEntry.display}, so it has no
                    rarities and no price data and a card captured as one could never be
                    identified, priced or listed. Captures are held until an export is in hand
                    and its vocabulary is authored in <code>pipeline/games.py</code>.
                  </p>
                ) : !gameEntry.catalogued ? (
                  <p className="capture-quiet">
                    {gameEntry.display} is captured and located like any other card and then
                    stops: no identification call, no join, no listing. Type a note under the
                    last capture saying what the card is — that note is the only thing it can
                    be found by later.
                  </p>
                ) : gameEntry.prompt === PROMPT_UNWRITTEN ? (
                  <p className="capture-quiet">
                    {gameEntry.display} has an export but no identification prompt yet, so
                    these cards will be captured and positioned now and identified later.
                  </p>
                ) : null}
              </OpenField>
            ) : (
              <Row
                k="G"
                label="Game"
                right={
                  gameEntry === null ? (
                    <span className="capture-val is-default">
                      {registryNote === null ? '…' : 'unavailable'}
                    </span>
                  ) : (
                    <span className="capture-val">{gameEntry.display}</span>
                  )
                }
                onToggle={() => toggleField('game')}
              />
            )}

            {/* The device picker's job, in the row grammar — the CameraPicker component's
                whole surface folded into this field so the sidebar has one control
                language. Everything it argued survives: the picker exists because the Cam
                Link presents the rig camera as a plain UVC webcam distinguishable only by
                label (D13, v1 bug 3 — no facingMode anywhere); nothing touches the camera
                until the operator asks (`started`, the open-on-mount permission prompt);
                a missing remembered device opens NOTHING rather than falling back to
                another lens; and the negotiated resolution is shown because a constraint
                is a request and a short stream should be caught before a box is shot
                through it. */}
            {openField === 'camera' ? (
              <OpenField
                k="V"
                label="Camera"
                meta={
                  signal !== null ? (
                    <span className={underTarget ? 'capture-meta-alert' : undefined}>
                      {signal.width} × {signal.height}
                    </span>
                  ) : !camera.started ? (
                    'not open'
                  ) : (
                    `${camera.devices.length} found`
                  )
                }
                onClose={closeField}
              >
                {!camera.started ? (
                  <>
                    <p className="capture-quiet">
                      The camera is not open yet. Nothing on this screen reaches for it until
                      you ask, so opening the app raises no permission prompt.
                    </p>
                    <button type="button" className="capture-go" onClick={camera.retry}>
                      Open the camera
                    </button>
                  </>
                ) : (
                  <>
                    <div className="capture-opts">
                      {camera.devices.map((device, position) => (
                        <Opt
                          key={device.deviceId}
                          k={position < 9 ? String(position + 1) : undefined}
                          on={device.deviceId === camera.deviceId}
                          /* Labels are blank until permission has been granted; useCamera
                             asks before enumerating, so a blank here means it was refused
                             — the numbered fallback keeps the list usable rather than
                             drawing a row of 64-character deviceIds. */
                          name={device.label === '' ? `Camera ${position + 1}` : device.label}
                          onPick={() => camera.selectDevice(device.deviceId)}
                        />
                      ))}
                      {camera.devices.length === 0 ? (
                        <p className="capture-quiet">No cameras found.</p>
                      ) : null}
                    </div>
                    {/* Selecting a device deliberately does NOT close this field: the
                        acquisition's outcome — an error, a short stream, or the resolution
                        in the meta — lands right here, and closing on the click would hide
                        the answer to the question the click asked. */}
                    {camera.missing ? (
                      <p className="capture-quiet">
                        The remembered camera is not connected. Check the Cam Link and that
                        the camera is awake, or pick a camera above. Nothing is open until
                        you do.
                      </p>
                    ) : null}
                    {camera.error === null ? null : (
                      <p className="capture-quiet">{camera.error}</p>
                    )}
                    {underTarget ? (
                      <p className="capture-quiet">
                        This stream is below the {PIPELINE_LONG_EDGE}px the pipeline works
                        from, so every photo will be worse than the rig can produce. Check
                        the camera is in its clean-HDMI output mode and that nothing else is
                        holding the capture card.
                      </p>
                    ) : null}
                    {/* Shown only when something is wrong — a permanently visible control
                        to reopen a WORKING camera is an invitation to drop the stream
                        mid-box. `retry` re-enumerates and re-opens, which is the only way
                        back from a stream error: re-picking the same device fires no
                        change event and re-runs nothing. */}
                    {camera.missing || camera.error !== null || underTarget ? (
                      <button type="button" className="capture-go" onClick={camera.retry}>
                        Reopen the camera
                      </button>
                    ) : null}
                  </>
                )}
              </OpenField>
            ) : (
              <Row
                k="V"
                label="Camera"
                right={
                  !camera.started ? (
                    <span className="capture-val is-default">not open</span>
                  ) : camera.missing || camera.error !== null ? (
                    // A one-word state at rest; the sentence, verbatim, is one keypress
                    // away inside the field. Accent because the system is unsure — its
                    // outline-weight job, never the fill.
                    <span className="capture-val capture-val-alert">fault</span>
                  ) : (
                    <span className="capture-val">
                      {camera.deviceId === null
                        ? 'none'
                        : (() => {
                            const chosen = camera.devices.find(
                              (device) => device.deviceId === camera.deviceId,
                            )
                            return chosen === undefined || chosen.label === ''
                              ? 'camera'
                              : chosen.label
                          })()}
                    </span>
                  )
                }
                onToggle={() => toggleField('camera')}
              />
            )}

            {/* Which way the stored photo is turned, in degrees clockwise. The rig's
                camera is side-mounted so a portrait card fills the field, the Cam Link
                reports the sensor's landscape frame regardless, and Gate B misread 45 of
                53 sideways cards — this setting is that lesson as a control. Display and
                encode turn together; the element's intrinsic frames are never touched. */}
            {openField === 'rotation' ? (
              <OpenField k="O" label="Rotation" meta="Choose one" onClose={closeField}>
                <Track
                  label="Rotation"
                  cells={ROTATIONS.map((value) => ({
                    text: `${value}°`,
                    on: camera.rotation === value,
                    onPick: () => {
                      camera.setRotation(value)
                      closeField()
                    },
                  }))}
                />
              </OpenField>
            ) : (
              <Row
                k="O"
                label="Rotation"
                right={<span className="capture-val">{camera.rotation}°</span>}
                onToggle={() => toggleField('rotation')}
              />
            )}

            {/* The trigger, last: the one session setting that is an ACT rather than a
                fact about the rig. Toggling out of motion is the disarm — reversible in
                one tap, so per docs/DESIGN.md it gets no confirmation — and toggling in
                starts a run (D19), which is why the mode never survives a reload. The
                answer to "how do I know it is on" is threefold: the pressed cell, the
                machine string on this row, and a HUD that only exists while the machine
                is watching. The row's value is `captureTrigger.name` verbatim — the
                `capture-trigger` class is load-bearing, app/tests/motion-live.spec.ts
                asserts the armed trigger through it. */}
            {openField === 'trigger' ? (
              <OpenField
                k="T"
                label="Trigger"
                meta={<span className="capture-trigger">{captureTrigger.name}</span>}
                onClose={closeField}
              >
                <Track
                  label="Trigger"
                  cells={[
                    {
                      text: 'key',
                      on: triggerMode === 'manual',
                      onPick: () => {
                        switchTrigger('manual')
                        closeField()
                      },
                    },
                    {
                      text: 'motion',
                      on: triggerMode === 'motion',
                      onPick: () => {
                        switchTrigger('motion')
                        closeField()
                      },
                    },
                  ]}
                />
              </OpenField>
            ) : (
              <Row
                k="T"
                label="Trigger"
                right={
                  <span
                    className={
                      triggerMode === 'manual'
                        ? 'capture-val is-default capture-trigger'
                        : 'capture-val capture-trigger'
                    }
                  >
                    {captureTrigger.name}
                  </span>
                }
                onToggle={() => toggleField('trigger')}
              />
            )}
          </div>
        </aside>

        {/* THE STAGE: live left, last capture right (spec 5.1), and nothing else. Everything
            that is not a photograph moved to the sidebar, so the frames get the whole of the
            column's height — which is what the stylesheet sizes them from.

            The wrapper is not decoration and is the one piece of markup here that exists for
            the stylesheet's sake: it is the size container the frame height is measured
            against. Without it there is no way to say "as tall as what is left" in CSS
            without a constant, and a constant is what was wrong with the layout this
            replaces. The stylesheet's `--portrait-h` block is the argument. */}
        <div className="capture-main">
          <div className={stageClass}>
            <section className="capture-panel">
              <p className="capture-panel-name">Live</p>
              <div className={frameClass}>
                {/* muted and playsInline are required for autoplay to start at all; neither is a
                    preference. No facingMode anywhere — v1 bug 3, and D13 records why: the Cam
                    Link presents the rig camera as a plain UVC webcam, indistinguishable by kind
                    from the laptop's own. */}
                <video className={liveMediaClass} ref={camera.videoRef} autoPlay playsInline muted />
                {/* The state of the frame, not an explanation of it — the picker in the sidebar
                    carries the explanation. `deviceId` is null when nothing is open at all, which
                    `useCamera` guarantees is never a silent stand-in for another camera. */}
                {camera.ready ? null : (
                  <p className="capture-frame-note">
                    {camera.deviceId === null ? 'No camera is open.' : 'Waiting for frames.'}
                  </p>
                )}
              </div>
            </section>

            <section className="capture-panel">
              <p className="capture-panel-name">Last capture</p>
              <div className={frameClass}>
                {last === undefined ? (
                  <p className="capture-frame-note">
                    Nothing captured in this session yet. The photo of each card lands here, big
                    enough to catch a blur or a finger before the card goes back in the box.
                  </p>
                ) : (
                  // The bytes the Mac stored, not the frame the browser holds. A local preview
                  // would show a photo even when the server recorded nothing, which is the one
                  // failure this screen exists to make loud.
                  <img
                    className="capture-media"
                    src={photoSrc(last.card.box, last.card.index, revision)}
                    alt={`Capture at ${last.card.label}`}
                  />
                )}
              </div>
              {last === undefined ? null : (
                <div className="capture-said">
                  {/* Rendered by pipeline/join.py and returned by the server. The app never
                      composes a second one. */}
                  <p className="capture-label">{last.card.label}</p>
                  <p className="capture-said-meta">
                    {/* The key rather than the display name, and first, because it is the
                        claim that decides whether this card is ever identified — and because
                        it is the string that lands in the sidecar and in `inventory.json`,
                        which is what the operator would grep. */}
                    <span>{last.game.key}</span>
                    <span>{last.setHint ?? 'no set hint'}</span>
                    {/* The same words the chip carries, so one state has one name. Read in the
                        finish slot beside "no set hint", which is what supplies the noun. */}
                    <span>
                      {last.finish.length === 0 ? NO_CLAIM_LABEL : last.finish.join(' · ')}
                    </span>
                    {last.card.new_box ? <span className="capture-flag">new box</span> : null}
                    {/* Every other flag here describes the capture; this one describes what the
                        server did with it. Kept beside them anyway, and per shot rather than as
                        one banner, because the session list has to stay honest about which
                        photograph took a position and which found one already taken. */}
                    {last.card.created ? null : (
                      <span className="capture-flag">already recorded</span>
                    )}
                  </p>

                  {/* THE NOTE, AND IT IS DELIBERATELY DOWN HERE RATHER THAN IN THE SIDEBAR.
                      Every control in that column is set once for a stack and then left
                      alone; a note is per card and is typed with a keyboard, and the feeder
                      emits every ~623 ms. Putting it before the shutter would make the run
                      wait for prose. So it corrects a card that is ALREADY photographed,
                      positioned and recorded — nothing about the next capture waits for it,
                      and leaving it empty costs nothing.

                      Its own `<form>`, so Enter saves and Enter cannot reach the shutter:
                      `CAPTURE_KEY` is a letter for exactly this reason (see its comment),
                      and typing a note is the one moment on this screen where a stray key
                      would otherwise photograph whatever is at the lens. */}
                  <form
                    className="capture-inline"
                    onSubmit={(event) => {
                      event.preventDefault()
                      void saveNote(last, noteDraft)
                      blurActive()
                    }}
                  >
                    <input
                      className="capture-text capture-note"
                      type="text"
                      placeholder={last.game.catalogued ? 'note' : 'what is this card?'}
                      aria-label={`Note on ${last.card.label}`}
                      value={noteDraft}
                      onChange={(event) => setNoteDraft(event.target.value)}
                    />
                    <button type="submit" className="capture-go" disabled={noteBusy}>
                      Save note <kbd className="capture-key">↵</kbd>
                    </button>
                  </form>

                  {/* Only for a game that is never identified. For everything else a note is
                      an optional extra and needs no explaining; for `misc` it is the ONLY
                      record of what the card is, and a silent text box would not say so. */}
                  {last.game.catalogued ? null : (
                    <p className="capture-quiet">
                      This card gets no identification call, so this note is the only thing
                      it can be found by later. A name and a game is enough.
                    </p>
                  )}

                  {noteSaved === null ? null : (
                    <p className="capture-quiet">
                      {noteSaved.text}
                      {noteSaved.code === null ? null : (
                        <span className="capture-halt-code"> {noteSaved.code}</span>
                      )}
                    </p>
                  )}
                </div>
              )}
            </section>
          </div>
        </div>
      </div>
    </main>
  )
}
