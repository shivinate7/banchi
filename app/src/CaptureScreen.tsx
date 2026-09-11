import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, ReactNode, RefObject } from 'react'

import { PositionLabel } from './PositionLabel'
import { storeKeyText } from './storeKey'
import type { BoxRecord, CardSummary, FinishClaim, GameEntry, GameRegistry } from './types'
import {
  getTcgSets,
  ServerError,
  capture,
  createBox,
  getBoxes,
  getGames,
  getStatus,
  newCaptureId,
  openSection,
  photoUrl,
  undoCapture,
  updateCard,
} from './server'
import { resolveSetHint } from './setHint'
import type { HintVerdict, SetOption } from './setHint'
import { manualTrigger } from './trigger'
import { motionTrigger } from './motion'
import { DEFAULT_CADENCE, cadenceTrigger } from './cadence'
import type { CadenceControls, CadenceDiagnostics } from './cadence'
import type { MotionControls, MotionDiagnostics, MotionPhase } from './motion'
import { MotionTrace } from './trace'
import { DEFAULT_PARAMS } from './motion'
import { useCamera, PIPELINE_LONG_EDGE, ROTATIONS } from './useCamera'
import {
  forgetCaptureSetup,
  rememberCaptureSetup,
  storedBoxRecency,
  storedCaptureSetup,
  touchBox,
} from './deviceMemory'
import type { CaptureSetup } from './deviceMemory'
import { captureBoxLabel } from './runScope'
import { Button, Icon, Kbd, Notice, Pill, Stat } from './kit'
import { toast } from './kit/toast'
import type { IconName, PillTone } from './kit'
import './CaptureScreen.css'

// The trigger seam (spec section 6). Gate B fired on this key and button; the motion
// machine (Gate C, src/motion.ts) sits in the same slot behind the mode toggle below.
//
// 'c' rather than Space or Enter, which are the obvious rig keys and lost for a specific
// reason: both activate whatever button currently has focus. Click Undo with the mouse and
// Space would then mean undo AND capture on every press — a double-fire that writes a
// position for a card nobody photographed. A letter key activates nothing.
const CAPTURE_KEY = 'c'
const UNDO_KEY = 'u'

const SECTION_KEY = 's'

const UNDO_DEPTH = 10

/** How long the settle ring takes to fill: the machine's own still window, in frames, at
 *  the 30 fps `motion.ts` derives its frame counts against. Written inline on the ring so
 *  it depicts the wait it stands for rather than a constant that finishes early or late. */
const SETTLE_MS = Math.round((DEFAULT_PARAMS.stillWindow * 1000) / 30)

// What the chips say. The key compared against `event.key` is lower case; the chip is not.
const CAPTURE_KEY_LABEL = 'C'
const UNDO_KEY_LABEL = 'U'
const SECTION_KEY_LABEL = 'S'

// Finish strings are rendered VERBATIM rather than as friendly labels: D3 rung 1 treats the
// claim as trusted, and the string on screen is the string written into the sidecar and
// quoted back by a review reason. Friendly labels would create a second vocabulary nothing
// audits — docs/DESIGN.md's own argument for showing reason codes as well as names.
//
// The list itself used to live here as `FINISHES`, Pokemon's three. It is per-game data now
// and comes from `GET /games`; see `finishChips` below.

const NO_CLAIM_LABEL = 'No claim'

/** A finish member drawn as a word. The KEY — `reverse_holo` — is what the claim stores,
 *  sends and compares (D3); only the eye gets the label. An unknown member falls back to
 *  the key with its underscores opened, so no game's vocabulary ever prints as a raw enum. */
const FINISH_LABEL: Record<string, string> = {
  normal: 'Normal',
  holo: 'Holo',
  reverse_holo: 'Reverse holo',
  foil: 'Foil',
}
function finishLabel(member: string): string {
  const known = FINISH_LABEL[member]
  if (known !== undefined) return known
  const opened = member.replace(/_/g, ' ')
  return opened.charAt(0).toUpperCase() + opened.slice(1)
}

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
 *  a second one, so with no capture response in hand there is nothing to show but the store
 *  key the server addressed it by — drawn with its sigil, never as a bare `#` (D92). */
type UndoTarget = { box: number; index: number; label: string | null }

/** What to call a position on screen — the server's own rendered label, or the record's own
 *  store key when there is no capture response holding one.
 *
 *  THE FALLBACK IS A KEY AND IT NOW SAYS SO (D92, swept 2026-09-04). It read `box 3, index 7`,
 *  which names `Place.index` — the `/inventory/<box>/<index>` path, the `<index>.jpg` the
 *  photograph is named after — in prose, on a screen whose every other number is D58's count.
 *  The two spaces disagree the moment a card is removed from a box, and this string is the
 *  accessible name of a control that removes cards. `B3 #7` is `storeKey.ts`'s own spelling of
 *  a key, so what the row draws and what a screen reader is told are one idea said twice.
 *
 *  It still cannot be mistaken for the rendered label: `Box 3 · Section 1 · Card 7` is a string
 *  only `pipeline/join.py` writes, and a client-side imitation of it would be a second copy of
 *  D10's divider size that nothing keeps in step. `PositionLabel` — which this feeds through
 *  `undoNote.position` — draws a bare key whole, because it peels one off a label only when
 *  there are position parts in front of it. */
function positionText(target: UndoTarget): string {
  return target.label ?? storeKeyText(target.box, target.index)
}

const BOX_DIGITS = /^[0-9]+$/

/** One row of the Box field: what the registry calls it, how full it is, whether it is shut.
 *
 *  `next` is the store's high-water mark and NOT a card count — the two disagree the moment
 *  a record is removed, which is why the row trails the server's own word for it. `sealed`
 *  is the fact this screen could not see until it started reading `GET /boxes`: D20 refuses
 *  a capture into a shut box before it computes an index, so offering one here bought a
 *  refusal at the shutter. */
type BoxOption = {
  box: number
  name: string | null
  next: number | undefined
  sealed: boolean
  /** Cards the box HOLDS — `BoxRecord.on_hand`, or its arithmetic where the server sent the
   *  parts and not the total. The hand order's second term (D-capture-setup-memory). `null`
   *  for a box this screen only knows about because `/status` named it: `GET /boxes` is what
   *  carries the count, and a box the registry did not return has none to read. Null sorts
   *  after every counted box rather than as zero, which is `BoxBrowse`'s rule for the same
   *  figure — an uncountable box is not known to be empty. */
  onHand: number | null
}

/** THE HAND'S ORDER OVER TWO BOXES, given what this browser remembers reaching for.
 *
 *  THREE TERMS, AND THE THIRD IS THE ONE BEING DEMOTED. Recency wins; where neither box has
 *  been reached for — or both were, in the same millisecond, which `Date.prototype.toISOString`
 *  makes possible and nothing else does — the fuller box leads; and the number decides what is
 *  left. `BoxBrowse.tsx`'s rail comparator is this, plus a search term this field has no
 *  equivalent of (its own exact match is hoisted separately, by `boxRows`).
 *
 *  A NEVER-TOUCHED BOX SORTS AFTER EVERY TOUCHED ONE because `''` is below every ISO stamp,
 *  and an UNCOUNTED one after every counted one because `-1` is below every count. Both are
 *  the same choice: the rank is what this browser KNOWS, and a box it knows nothing about does
 *  not get to lead on an absence.
 *
 *  A PLAIN FUNCTION RATHER THAN A HOOK, so the box field and anything that later wants this
 *  order can share one comparator without either owning it, and so it is readable straight
 *  through — a sort this screen's whole list depends on should not be spread across a closure
 *  and three dependency arrays. */
function handOrder(
  recency: ReadonlyMap<number, string>,
): (left: BoxOption, right: BoxOption) => number {
  return (left, right) => {
    const ra = recency.get(left.box) ?? ''
    const rb = recency.get(right.box) ?? ''
    if (ra !== rb) return ra > rb ? -1 : 1
    const ha = left.onHand ?? -1
    const hb = right.onHand ?? -1
    if (ha !== hb) return hb - ha
    return left.box - right.box
  }
}

/** Why the set suggestions are missing, in the operator's terms (D65).
 *
 *  SENTENCES, NOT FILE PATHS. The session lives in `.env`, and that is a fact for the person
 *  setting the rig up rather than the one at the lens. Each case is stated plainly and no
 *  more — the field still works — and the code is kept on the end of anything unnamed
 *  because `docs/DESIGN.md` shows reason codes beside names, so what you saw stays greppable.
 *  **THAT RULE IS OLDER THAN THIS COMMENT AND IT SURVIVED A SESSION WRITING OVER IT**: the
 *  build that widened this map first wrote `set PKMNSCAN_TCG_USER_AGENT in .env` into two of
 *  these clauses, which is the remedy for the person at the keyboard and noise to the person
 *  holding a card over a stand. It says what is wrong; where the knob is lives one layer down.
 *
 *  EVERY CODE `server/tcg_export.py:filters` CAN RAISE IS NAMED HERE, and until 2026-09-06
 *  two of the nine were. The other seven fell to the unknown-code tail — which is a designed
 *  fallback and not a defect, but it is the FLOOR, and seven of nine landing on the floor
 *  means the map had stopped being the answer. `make docs-audit`'s `hint reasons` row
 *  reconciles this map against the codes that route can send, in both directions, so a tenth
 *  cannot arrive unlabelled and a branch cannot go dead unnoticed.
 *
 *  `message` IS UNDER THE FLOOR AND ABOVE THE BARE CODE. The route carries the transport's
 *  own sentence now, so a code this map has not caught up with reads as words rather than as
 *  a token — with the code still beside it, because greppable is the rule above. It is not
 *  what the operator normally reads and it must not become that: a sentence written for the
 *  pipeline's reader names `.env` and this screen does not.
 *
 *  THE REGISTER IS THE RIG'S. Each clause ends mid-sentence — the caller appends *"The hint
 *  is stored exactly as typed"* — and none of them asks the operator to stop capturing. That
 *  is the whole shape of this failure: the hint field still works, typed by hand, and the
 *  autocomplete is what is missing. */
function hintReason(code: string | null, message?: string | null): string {
  if (!code) return ''
  // The session — the likeliest of these by far, and the only ones the old map named.
  if (code === 'tcg_session_expired') return 'The TCGplayer session has expired — sign in again'
  if (code === 'tcg_cookie_missing') return 'No TCGplayer session'
  if (code === 'tcg_cookie_malformed') return 'The stored TCGplayer session is not a whole one'
  // The portal, or the way out to it. None of it is fixed at the lens, so none of it carries a
  // verb the operator cannot perform here: they say what is wrong and stop.
  if (code === 'tcg_blocked') return 'TCGplayer refused this client'
  if (code === 'tcg_unavailable') return 'TCGplayer is down — the set list will come back'
  if (code === 'tcg_unreachable' || code === 'unreachable') return 'TCGplayer could not be reached'
  if (code === 'tcg_unexpected_response') return 'TCGplayer answered with something unreadable'
  if (code === 'tcg_filters_unreadable') return 'TCGplayer changed the shape of its set list'
  // This machine's own, and deliberately not naming the variable — see the rule above.
  if (code === 'tcg_url_invalid') return 'The set list is pointed somewhere the session may not go'
  if (code === 'no_category') return 'No TCGplayer category for this game'
  // THE FLOOR, and reaching it means `hint reasons` is already failing a commit. The
  // transport's sentence beats the bare token; the token stays beside it either way.
  return message
    ? `${message.trim().replace(/\.$/, '')} (${code})`
    : `Set list unavailable (${code})`
}

function hintMetaText(verdict: HintVerdict): string {
  // Short enough not to squeeze the entry — `.capture-entrymeta` never wraps, and the box
  // beside it is where the operator is typing.
  // `no hint` rather than `optional`, which the head row two lines up already says: the meta
  // reports the STATE of what is typed, and repeating the field's own modality there would
  // spend the one line beside the entry on a word already on screen.
  if (verdict.state === 'blank') return 'no hint'
  if (verdict.state === 'unchecked') return 'not checked'
  if (verdict.state === 'ambiguous') return `${verdict.among.length} sets`
  if (verdict.state === 'unmatched') return 'names no set'
  return verdict.exact ? 'names a set' : 'enter completes'
}

/** The same verdict as a sentence, in the operator's terms rather than the matcher's.
 *  `game` is the registry's display name — `Pokémon`, `Riftbound` — because "widens to the
 *  whole category" is TCGplayer's word for a thing the operator calls a game. */
function hintNoteText(verdict: HintVerdict, game: string): string {
  if (verdict.state === 'blank') {
    return (
      'Optional, and it has to name a set TCGplayer publishes. Left empty, a collector ' +
      'number that matches rows in two sets comes back as a review rather than a listing.'
    )
  }
  if (verdict.state === 'unchecked') return 'Stored exactly as typed.'
  if (verdict.state === 'matched') {
    // THE SECOND SENTENCE USED TO SAY THE JOIN READ ONLY THE FULL NAME, and it was true when
    // it was written: the fetch and the join were two matchers with two rule sets, so a code
    // scoped the export and then failed to narrow the rows it had fetched. They are one
    // ladder now (`pipeline/setnames.py`), so completing is a courtesy to the next reader of
    // the sidecar rather than something the pipeline needs.
    return verdict.exact
      ? `Names ${verdict.set}, and the export will scope to that set.`
      : `Resolves to ${verdict.set}, and the export will scope to that set. Enter writes the name out.`
  }
  if (verdict.state === 'ambiguous') {
    // The ambiguity is the whole message, so the sets themselves are named: `Origins` and
    // `Origins: Proving Grounds` is the shape, and knowing which two is how you pick one.
    return (
      `${verdict.among.length} sets answer to that — ${verdict.among.slice(0, 3).join(', ')}` +
      `${verdict.among.length > 3 ? ', …' : ''} — so it names none of them, and the export ` +
      `widens to all of ${game}.`
    )
  }
  return (
    `No set of ${game} answers to that. It is still stored and still sent to the model; ` +
    `what it will not do is scope the export, which widens to the whole game.`
  )
}

/* ONE KEY IS LEFT IN `sessionStorage`, AND IT IS THE ONE D27 WAS ACTUALLY ABOUT.
 *
 * THAT ENTRY PUT SEVEN HERE AND THE OWNER HAS SINCE OVERRULED SIX (D-capture-setup-memory):
 * *"ideally let it save my last used on capture on all settings ... so the game i picked,
 * camera i picked, all stay saved in some sorta session history"*. D27's argument for session
 * scope was that *"a new tab is a new shift and closing the browser ends one"*, and the
 * operator's own report is that the premise is wrong — a shift ends when they stop feeding
 * cards, which is neither of those moments. The six SETTINGS moved to `deviceMemory.ts`'s
 * `banchi.capture.setup`, beside the camera and the rotation `useCamera.ts` has kept in
 * `localStorage` since before that carve-out was generalised, for this reason.
 *
 * `captureId` DID NOT MOVE, AND IT IS THE VALUE THE CARVE-OUT EXISTS FOR. It is the in-flight
 * id of a capture whose response was lost. D27 records what losing it costs — the ambiguity
 * becomes permanently unresolvable, and D10's high-water mark hands the burned position to the
 * next physical card — and everything about it is scoped to ONE PAGE: it is minted for a
 * photograph being taken now, it is answered or abandoned within seconds, and the banner it
 * raises asks the operator to put THAT card back at the lens.
 *
 * SO A RESTORED ONE IS STRICTLY WORSE THAN NONE, which is the argument the six cannot make. A
 * setting restored into a new shift is at worst a stale claim that is on screen and one press
 * from being right. This restored into a new shift is a banner about a card that was at the
 * lens yesterday, asking for a card nobody is holding — and the honest answer to it, feeding
 * that card again, would burn a position on a capture that resolved hours ago. Session scope
 * is what holds the window to "this page load", which is the window the banner's own sentence
 * is true in.
 *
 * THE `pkmnscan.` PREFIX WAS RENAMED TO `banchi.` ON 2026-09-06, ON THE OWNER'S WORD, AND
 * NOTHING MIGRATES. `useCamera.ts` carries the argument in full beside its own two keys; the
 * short of it is that the split between `banchi.*` and `pkmnscan.*` was chronological rather
 * than principled, and the owner declined a read-time fallback because a fallback can never
 * safely be deleted afterwards. */
const SESSION_KEYS = {
  captureId: 'banchi.session.captureId',
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
 * finish claim from before the game was changed.
 *
 * `deviceMemory.ts` VALIDATES THE SHAPE AND THIS SCREEN VALIDATES THE MEANING, and the split
 * is where the knowledge is. That file can say a box is a safe integer 1 or higher and that a
 * claim is a list of strings, because those are rules about the value itself. It cannot say
 * whether box 7 still exists, is still open, or has been deleted and its number handed to a
 * different drawer — nor whether `Illustration Rare` is still a rarity `pipeline/games.py`
 * authors. Every one of those is asked HERE, against the answer that arrives, by the same
 * check the live control makes:
 *
 *   - the game, in `loadGames`, which falls back to the registry's own default
 *   - the two claims, in the pair of effects beside `offeredFinishes`, member by member
 *   - the box, in `restoredBoxCheck` below, once `GET /boxes` has actually answered
 */

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

/** Which field is open. One at a time, by construction: the state is a single id, so a
 *  second field cannot be open without closing the first — the mockup's rule enforced by
 *  the type rather than by bookkeeping. */
type FieldId =
  | 'box'
  | 'set'
  | 'rarity'
  | 'finish'
  | 'game'
  | 'product'
  | 'camera'
  | 'rotation'
  | 'trigger'

/* The field letters, none of which may be `c`, `u` or `s` — those are the run's own keys and
 * stay reserved (see CAPTURE_KEY). `v` for the camera because `c` is taken, `o` for rotation
 * because `r` is, and `h` for the set hint because `s` is: the mnemonic bends before an act
 * does, three times now. The `,` leader chord (App.tsx) is consumed in the capture phase
 * before any of these are offered a key, so `,` then `b` navigates and does not also open the
 * box field. */
const FIELD_KEYS: Readonly<Record<string, FieldId>> = {
  b: 'box',
  h: 'set',
  r: 'rarity',
  f: 'finish',
  g: 'game',
  /* C10's product claim, and `p` was free. It costs one key out of `OPTION_KEYS`, at
   * position 20 — past the longest authored vocabulary in the registry (thirteen), so no
   * option row that exists today moves. `app/tests/capture-claims.spec.ts` pins the tenth
   * through thirteenth rarities to `0 a d e` and is unaffected for the same reason. */
  p: 'product',
  v: 'camera',
  o: 'rotation',
  t: 'trigger',
}

const RESERVED_KEYS: ReadonlySet<string> = new Set([
  ...Object.keys(FIELD_KEYS),
  CAPTURE_KEY,
  UNDO_KEY,
  SECTION_KEY,
])

const OPTION_KEYS: readonly string[] = [...'1234567890abcdefghijklmnopqrstuvwxyz'].filter(
  (key) => !RESERVED_KEYS.has(key),
)

/** Key -> position, so the keydown handler is a lookup rather than a scan of the array on
 *  every press. Built once, from the array above, so the two can never disagree. */
const OPTION_INDEX: ReadonlyMap<string, number> = new Map(
  OPTION_KEYS.map((key, position) => [key, position]),
)

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

/* ---- the rail's grammar: a row at rest, an open field, an option, a track ----
 *
 * `aria-expanded` on every row and `aria-pressed` on every option are facts about the
 * document, and the stylesheet selects on them rather than on state classes. */

/** A field at rest: keycap · label · current value · chevron. A button, because the whole
 *  line is the control that opens it. */
/** Which implementation is behind the trigger seam. Three since D130: the key, the settle
 *  machine, and the beat-locked cadence. Never persisted — arming is an act (D19). */
type TriggerMode = 'manual' | 'motion' | 'cadence'

/** What the HUD reads. The settle machine's readout, and the cadence's fields where that is
 *  the trigger armed — optional, so one state serves both machines and the HUD renders the
 *  beat's spans only when they exist. */
type HudDiag = MotionDiagnostics & Partial<Omit<CadenceDiagnostics, keyof MotionDiagnostics>>

function triggerIcon(mode: TriggerMode): IconName {
  return mode === 'motion' ? 'eye' : mode === 'cadence' ? 'clock' : 'keyboard'
}

function Row({
  k,
  label,
  icon,
  right,
  onToggle,
  size,
}: {
  k: string
  label: string
  icon?: IconName
  right: ReactNode
  onToggle: () => void
  size?: 'lg'
}) {
  return (
    <button
      type="button"
      className={size === 'lg' ? 'capture-row capture-row-lg' : 'capture-row'}
      aria-expanded={false}
      aria-keyshortcuts={k}
      onClick={onToggle}
    >
      <Kbd className="capture-k">{k}</Kbd>
      {icon === undefined ? null : <Icon name={icon} size={15} className="capture-row-icon" />}
      <span className="capture-lab">{label}</span>
      <span className="capture-right">{right}</span>
      <Icon name="chevronDown" size={14} className="capture-chev" />
    </button>
  )
}

/** The one open field: the same row as its head (now closing), and the field's own body
 *  under it. */
function OpenField({
  k,
  label,
  icon,
  meta,
  onClose,
  children,
  size,
}: {
  k: string
  label: string
  icon?: IconName
  meta: ReactNode
  onClose: () => void
  children: ReactNode
  size?: 'lg'
}) {
  return (
    <div className={size === 'lg' ? 'capture-open capture-open-lg' : 'capture-open'}>
      <button
        type="button"
        className="capture-row"
        aria-expanded={true}
        aria-keyshortcuts={k}
        onClick={onClose}
      >
        <Kbd className="capture-k">{k}</Kbd>
        {icon === undefined ? null : <Icon name={icon} size={15} className="capture-row-icon" />}
        <span className="capture-lab">{label}</span>
        <span className="capture-meta">{meta}</span>
        <Icon name="chevronUp" size={14} className="capture-chev" />
      </button>
      <div className="capture-open-body">{children}</div>
    </div>
  )
}

/** One option row inside an open field: keycap (or none), the selection mark, the name, an
 *  optional machine trail on the right. Past the end of `OPTION_KEYS` there is no keycap
 *  at all — drawn keyless rather than with a key that does nothing. */
function Opt({
  k,
  on,
  name,
  sfx,
  trail,
  trailWord = false,
  onPick,
}: {
  k?: string
  on: boolean
  name: string
  /** The de-emphasised shared suffix — ` Rare` on eleven of Pokemon's thirteen. */
  sfx?: string | null
  trail?: string
  /** The trail is a word (`Premium`) rather than a key (`pokemon`, `next 12`). */
  trailWord?: boolean
  onPick: () => void
}) {
  return (
    <button type="button" className="capture-opt" aria-pressed={on} onClick={onPick}>
      {k === undefined ? (
        <span className="capture-k capture-k-blank" aria-hidden="true" />
      ) : (
        <Kbd className="capture-k">{k}</Kbd>
      )}
      <span className="capture-mark" aria-hidden="true">
        <Icon name="check" size={11} strokeWidth={3} />
      </span>
      <span className="capture-opt-name">
        {name}
        {sfx == null ? null : <span className="capture-sfx">{sfx}</span>}
      </span>
      {trail === undefined ? null : (
        <span className={trailWord ? 'capture-opt-trail is-word' : 'capture-opt-trail'}>{trail}</span>
      )}
    </button>
  )
}

/** A segmented track for single-selects whose whole vocabulary fits one line (finish,
 *  rotation, trigger). `aria-pressed` buttons in a named group; a disabled cell stays
 *  rendered, dimmed, refusing — never hidden. */
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
      <div className="capture-track bn-seg" role="group" aria-label={label}>
        {cells.map((cell) => (
          <button
            key={cell.text}
            type="button"
            className="capture-cell bn-seg-item"
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

/** WHAT AN UNDO THUMBNAIL DRAWS UNDER THE CARD — the whole figure, sigil and all, because the
 *  two cases it covers are two different numbers and they may not wear one sigil (D92).
 *
 *  OUT OF A RENDERED LABEL IT IS A COUNT. `Box 3 · Section 1 · Card 40` ends on D58's countable
 *  number — the fortieth card in the box, which is what a hand counts to — and a bare `#40` is
 *  exactly what that sigil means on every other screen in the product.
 *
 *  WITH NO LABEL THERE IS NO COUNT TO DRAW, AND THIS DREW ONE ANYWAY. `undoStack` builds one
 *  target from the server's high-water mark alone when this session never saw the capture
 *  response — `{ box, index, label: null }` — and all it holds is `Place.index`, the store key.
 *  That went out as `#7`: the key wearing the count's sigil, on the one screen where the two
 *  spaces provably differ, which is the single confusion D92 exists to end. It draws `B3 #7`
 *  now, through the one function that spells a key.
 *
 *  `scripts/sigil-check.py` never saw it and could not have: it matches the text inside a `#{…}`
 *  and the text here was a call to this function, not the word `index`. That is the ceiling
 *  `docs/DEBTS.md` §9 wrote down in advance, not a new hole.
 *
 *  THE TAIL MUST BE `<word> <number>` TO BE PROMOTED. `/(\d+)$/` alone would take the `31` off
 *  a `… · departed · B3 #31` tail and print `#31` — a bare sigil over a key by the other door.
 *  No undo target carries a departed label today, because a card captured this session has not
 *  left the box; the guard costs a character class and does not depend on that staying true. */
function undoFigure(target: UndoTarget): string {
  if (target.label !== null) {
    const tail = target.label.split(' · ').pop() ?? ''
    const match = /^\D+ (\d+)$/.exec(tail)
    if (match !== null && match[1] !== undefined) return `#${match[1]}`
  }
  return storeKeyText(target.box, target.index)
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

  /* THE SETUP THIS BROWSER HAD LAST TIME, read once and then owned by the six `useState`s
     below (D-capture-setup-memory). One `localStorage` document rather than six keys, because
     it is one habit — `deviceMemory.ts` carries that argument beside `banchi.orders.
     fetch-filter`, which makes it for its own two fields.

     PASSED AS A FUNCTION, NOT CALLED. An initialiser EXPRESSION is evaluated on every render
     and thrown away, and this one touches a synchronous store; a function is read on the first
     render and never again. That was already the rule for the per-key readers this replaced,
     and it matters more now that one read serves six values. */
  const [restored] = useState<CaptureSetup>(storedCaptureSetup)

  // Box, game, set hint and finish are client state resent on every capture (spec 5.2). The
  // server holds no notion of a current box, which is what lets two devices work without a
  // session.
  const [box, setBox] = useState<number | null>(restored.box)
  const [boxNote, setBoxNote] = useState<string | null>(null)
  // Creating a box is now a REQUEST, where it used to be a local assignment: a name has to
  // reach the store before anything can be captured into it, and it can be refused
  // (`name_taken`). This gates the entry's Enter so a double press cannot post twice.
  const [boxBusy, setBoxBusy] = useState(false)
  const [setHint, setSetHint] = useState(restored.setHint)

  
  const [tcgSets, setTcgSets] = useState<
    Record<
      string,
      {
        sets: SetOption[]
        aliases: Record<string, string>
        reason: string | null
        message: string | null
      }
    >
  >({})
  /* THE NAMES AND THE ALIAS TABLE ARE KEPT APART, where this used to concatenate them into
     one list of strings for the `datalist` and throw the distinction away. `resolveSetHint`
     needs them apart: an alias resolves to another HINT and the shape rules then match THAT,
     which is `server/tcg_export.py:match_sets`'s rule zero and cannot be expressed over a
     flattened list. The suggestions are still the concatenation — see `hintSuggestions`. */
  const loadSets = useCallback(
    (forGame: string) => {
      if (!forGame || tcgSets[forGame] !== undefined) return
      void getTcgSets(forGame)
        .then((answer) =>
          setTcgSets((prev) => ({
            ...prev,
            [forGame]: {
              sets: answer.sets.map((row: { name: string }) => ({ name: row.name })),
              aliases: answer.aliases ?? {},
              reason: answer.reason,
              message: answer.message ?? null,
            },
          })),
        )
        .catch(() =>
          setTcgSets((prev) => ({
            ...prev,
            // THE ONE CODE THE SERVER NEVER SENDS. The request itself failed — the capture
            // server is down or the page is offline — so there is no transport sentence to
            // carry, and `hintReason` names this string beside `tcg_unreachable` because the
            // operator cannot tell the two apart and does not need to.
            [forGame]: { sets: [], aliases: {}, reason: 'unreachable', message: null },
          })),
        )
    },
    [tcgSets],
  )
  // EMPTY, not ['normal']. See NO_CLAIM_LABEL above: the default has to be "the operator
  // has said nothing", or D3's rungs 2 and 3 are dead for every card this rig ever sees.
  // A SET since the amendment of 2026-08-23 — any number of members is legal, including all
  // of them, and toggling the last one off IS the clear, exactly as the rarity claim beside
  // it behaves. That sameness is D3's stated point, not a coincidence of implementation.
  const [finish, setFinish] = useState<FinishClaim>(() => [...restored.finish])

  /* D23's stack claim: which of the chosen game's rarities this pre-sorted stack may hold.
   * Empty is NO CLAIM — the wire omits the key, the sidecar records nothing, and the ladder
   * walks exactly as it did before the field existed. Any number of members is legal,
   * including all of them; toggling the last one off IS the clear, so the control needs no
   * separate reset. Restored from `sessionStorage` (D27) and validated against the registry
   * by the effect beside the finish one, exactly as the finish claim is. */
  const [rarityClaim, setRarityClaim] = useState<string[]>(() => [...restored.rarityClaim])

  /* WHICH FIELD IS OPEN, or null for the all-at-rest column. One id rather than a set —
   * pass D's one-field-open rule enforced by the shape of the state. Session-only and
   * deliberately not persisted: an open picker is a moment, not a claim. */
  const [openField, setOpenField] = useState<FieldId | null>(null)

  
  const [boxEntry, setBoxEntry] = useState('')

  
  const [boxRecords, setBoxRecords] = useState<BoxRecord[]>([])

  /* WHETHER `GET /boxes` HAS ACTUALLY ANSWERED, which `boxRecords` cannot say: `[]` is both
     the starting value and what a store with no boxes returns. Only the restored-box check
     reads it, and only because judging a restore against a list that has not arrived would
     clear a good box on every slow fetch. */
  const [boxesSeen, setBoxesSeen] = useState(false)

  /* WHY THE RESTORED BOX WAS LET GO OF, if it was. Separate from `boxNote` on purpose: that
     one explains ONE REJECTED ENTRY and is cleared by every change of `openField`, including
     the change this check itself makes — so a restore message written into it would be wiped
     by the very act of opening the field to show it. This is about the arrival, and it lives
     until a box is chosen. */
  const [restoreNote, setRestoreNote] = useState<string | null>(null)

  /* WHICH BOXES THIS BROWSER HAS REACHED FOR, newest first, shared with `#/inventory`'s rail
     (D-capture-setup-memory). Read once into state and advanced by `touchBox`'s return value
     rather than re-read after every write — `BoxBrowse.tsx` does the same, and it is what keeps
     the order from depending on a second round trip through `localStorage`. */
  const [recency, setRecency] = useState<ReadonlyMap<number, string>>(storedBoxRecency)

  
  const [game, setGame] = useState<string | null>(restored.game)
  /* C10's product claim, and it behaves exactly like `game` above: session state, resent
   * with every capture, written to the record and the sidecar, correctable afterwards on the
   * card that got it wrong. `null` is NO CLAIM and is never defaulted to `booster` — being
   * right most of the time is precisely the problem, because the times it is wrong a $1.50
   * Pokemon Center ETB code leaves in a penny lot and nobody finds out. The Codes screen
   * counts unclaimed codes and refuses to put them in either lane for the same reason. */
  const [product, setProduct] = useState<string | null>(restored.product)

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
  const haltRef = useRef<HTMLElement>(null)
  /* Display only. When a halt lands the keyboard goes to Resume — `role="alert"` already
   * speaks it; this is for the hands — and the halt's height is handed to the page as
   * `--cap-halt-h`, so the viewfinder and the last capture shrink to stay whole above the
   * fold instead of being pushed under it. Observed rather than measured once: opening
   * "What the server said" grows the block. */
  useEffect(() => {
    if (halt === null) return
    const node = haltRef.current
    const page = node?.closest<HTMLElement>('.capture') ?? null
    if (node === null || page === null) return
    node.querySelector<HTMLButtonElement>('.capture-resume')?.focus({ preventScroll: true })
    /* On a phone the halt lands at the top of a page that is usually scrolled down to the
     * shutter, so it is brought into view — `.capture-halt`'s scroll-margin keeps it clear of
     * the top bar. On wider screens the two frames shrink instead (see --cap-halt-h). */
    if (window.matchMedia('(max-width: 767px)').matches) {
      node.scrollIntoView({ block: 'start', behavior: 'smooth' })
    }
    const write = () => page.style.setProperty('--cap-halt-h', `${node.offsetHeight}px`)
    write()
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(write)
    observer?.observe(node)
    return () => {
      observer?.disconnect()
      page.style.removeProperty('--cap-halt-h')
    }
  }, [halt])
  const [busy, setBusy] = useState(false)
  // `position` is the rendered label of what was deleted, shown separately from `text` so it
  // can carry the utility face inside a body sentence. Null on a refusal, where the whole
  // message is the server's own and names its own position.
  // `did` and `want` are 1 and 1 for the ordinary press and differ only for a walk-back that
  // stopped early — the one outcome the operator cannot see for themselves, because the
  // cards that went and the cards that did not both leave the list.
  const [undoNote, setUndoNote] = useState<
    (Note & { done: boolean; position: string | null; did: number; want: number }) | null
  >(null)
  const [revision, setRevision] = useState(0)
  /* Bumped on every capture the server answered, and only then: the viewfinder flashes
   * on it. Undo bumps `revision` (the photo URL must change) and never this. */
  const [flash, setFlash] = useState(0)

  
  const [sectionNote, setSectionNote] = useState<
    (Note & { done: boolean; place: string | null }) | null
  >(null)
  const [sectionBusy, setSectionBusy] = useState(false)

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
  const [triggerMode, setTriggerMode] = useState<TriggerMode>('manual')

  // The machine's own counters and live signal, for the HUD. Null until the first frame
  // reaches the machine, which is also the "is it actually seeing anything" indicator.
  const [motionDiag, setMotionDiag] = useState<HudDiag | null>(null)
  /* The operator's pinned beat period, as typed. Empty is "measure it", which is the default
   * and what the seed stands in for until the beat has been heard (D130). Device-local like
   * the rest of this screen's session claims, and NOT persisted: a period is a fact about
   * tonight's feeder, and arming is an act (D19). */
  const [periodPin, setPeriodPin] = useState('')

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
    (mode: TriggerMode) => {
      if (mode === triggerMode) return

      setTriggerMode(mode)
      setMotionDiag(null)
      setSwallowed({ busy: 0, halted: 0, noBox: 0, notReady: 0, held: 0 })
      // The trace belongs to one armed session, exactly like the machine's own counters:
      // arming starts a fresh recording, disarming keeps the old one around so it can
      // still be saved after the run stops. The file says which machine recorded it.
      if (mode === 'motion') traceRef.current = new MotionTrace(DEFAULT_PARAMS, 'motion')
      if (mode === 'cadence') traceRef.current = new MotionTrace(DEFAULT_CADENCE, 'cadence')
    },
    [triggerMode],
  )

  /* D19's Tier-1 tuning instrument. A ref, not state: it takes ~30 writes a second and
   * nothing re-renders on its account — the HUD's frame counter already moves via the
   * throttled diagnostics. */
  const traceRef = useRef<MotionTrace | null>(null)

  /* The armed machine's own control surface — today only `rebaseline`. Null whenever motion
   * is not armed, which is exactly when the control below must not render. */
  const motionControls = useRef<MotionControls | CadenceControls | null>(null)

  // Read synchronously inside the capture path. React state cannot serve here: two fires in
  // one tick — a key repeat, or a focused button activated by the same press — would both
  // read the stale `false` and send two photos of one card.
  const busyRef = useRef(false)

  
  const captureIdRef = useRef<string | null>(readSessionCaptureId())

  
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

  
  /* THE SETUP, WRITTEN WHOLE ON EVERY CHANGE TO ANY OF IT (D-capture-setup-memory). One
     document, so the six can never be stored half-updated and the clear is one removal rather
     than six that can fail apart.

     THE VALUES GO IN AS THE SCREEN HOLDS THEM, empty lists and all — unlike the six session
     keys this replaced, which each stored "empty" as ABSENT so a cleared field and an
     unwritten one read alike. That trick bought nothing here: the document is present or it is
     not, and `storedCaptureSetup` reads a missing field as the same nothing it reads a missing
     document as.

     IT RUNS ON MOUNT TOO, writing the restored setup straight back. Harmless and deliberate —
     it is the same value, and the alternative is a ref that exists only to skip one write. */
  useEffect(() => {
    rememberCaptureSetup({ box, game, setHint, finish, rarityClaim, product })
  }, [box, setHint, finish, game, rarityClaim, product])

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

  
  const pickGame = useCallback((key: string) => {
    setGame(key)
    setFinish([])
    setRarityClaim([])
  }, [])

  
  const offeredFinishes = useMemo<ReadonlySet<string> | null>(() => {
    if (gameEntry === null || rarityClaim.length === 0) return null
    const rows = rarityClaim.map((rarity) => gameEntry.finish_by_rarity[rarity])
    if (rows.some((row) => row === undefined)) return null
    const union = new Set<string>()
    for (const row of rows) for (const member of row ?? []) union.add(member)
    return union
  }, [gameEntry, rarityClaim])

  
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

  
  /* THE BOX LIST, IN THE ORDER THE OPERATOR'S HAND WORKS (D-capture-setup-memory).
   *
   * THE OWNER ASKED FOR THIS SORT BY NAME: *"same box style sorting in inventory (where most
   * recently selected/most filled go to the top, rather than box #, determines the order of
   * box in Workflow: Capture)"*. It is `BoxBrowse.tsx`'s rail rule and it is the SAME rule
   * rather than a second one — the box this browser last reached for, then the box holding the
   * most cards, then the number, which is the last thing the owner thinks in and so the last
   * thing this sorts by. `deviceMemory.ts:storedBoxRecency` is the one store both read.
   *
   * WHAT IT REPLACES WAS A PROXY THAT SAID SO IN ITS OWN COMMENT. The list was sorted by
   * number and `boxRows` took the highest nine, on the reasoning that *"boxes are allocated
   * upward and recency is not a fact either route carries"*. That was true of the ROUTES and
   * stopped being true of the browser when D132 started recording which boxes the hand opened.
   * The proxy fails exactly where it matters: a long-running drawer the operator has fed for
   * three weeks sinks below every box made since, and the only box that can never sink is the
   * one made last — which is the one case a person does not need help finding.
   *
   * `on_hand` AND NOT `cards`, `fill` OR `next_index`, for `BoxBrowse`'s reason: a box full of
   * sold records is not a box worth reaching for, and the three others count records that have
   * left. `next_index` is the allocator's high-water mark and is what the ROW still trails,
   * which is a different job — it says where the next photograph lands. */
  const boxOptions = useMemo(() => {
    const byNumber = new Map<number, BoxOption>()
    for (const record of boxRecords) {
      if (!Number.isInteger(record.box)) continue
      byNumber.set(record.box, {
        box: record.box,
        name: record.name,
        next: record.next_index,
        sealed: record.state === 'closed',
        /* The server's own count first, its arithmetic second — `BoxBrowse` does the same, and
           for the same reason: `on_hand` is nullable because an uncountable box is not an
           empty one, and a payload predating the field is not either. */
        onHand:
          record.on_hand ?? record.cards - record.sold - record.retired - (record.moved ?? 0),
      })
    }
    for (const key of Object.keys(nextIndex)) {
      const value = Number(key)
      if (!Number.isInteger(value)) continue
      const known = byNumber.get(value)
      if (known === undefined) {
        byNumber.set(value, {
          box: value,
          name: null,
          next: nextIndex[key],
          sealed: false,
          onHand: null,
        })
      } else {
        known.next = nextIndex[key]
      }
    }
    return [...byNumber.values()].sort(handOrder(recency))
  }, [boxRecords, nextIndex, recency])

  const boxes = useMemo(() => boxOptions.map((option) => option.box), [boxOptions])

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

  // An entry belongs to one opening. Cleared on every change of `openField` — including to
  // null — so no field ever reopens pre-narrowed by a search the operator cannot see the
  // reason for. `boxNote` rides along: it explains one rejected entry, not a field.
  useEffect(() => {
    setBoxEntry('')
    setBoxNote(null)
  }, [openField])

  
  const boxEntryRef = useRef<HTMLInputElement>(null)
  const hintRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (openField === 'box') boxEntryRef.current?.focus()
    else if (openField === 'set') {
      hintRef.current?.focus()
      /* THE VOCABULARY FOLLOWS THE FIELD BEING OPEN, not the row being tapped. `H` opens it
         from the key handler and never touches the row's `onToggle`, so hanging the load off
         the tap left the list empty for every operator who uses the keyboard — which on this
         screen is all of them. Keyed on the effect that already fires for both paths. */
      if (game !== null) loadSets(game)
    }
  }, [openField, game, loadSets])

  /* WHETHER WHAT IS TYPED NAMES A REAL SET, ANSWERED WHILE IT IS BEING TYPED.
   *
   * `undefined` until the field has been opened once for this game, which is D65's laziness
   * and not a defect: most sessions never touch the hint, and the vocabulary costs a
   * TCGplayer round trip. `resolveSetHint` reads an absent vocabulary as `unchecked` — the
   * verdict that says THIS SCREEN CANNOT TELL — so the loading window, a game with no sets
   * and an expired session all render as silence rather than as an accusation. */
  const hintVocabulary = game === null ? undefined : tcgSets[game]
  const hintVerdict = useMemo<HintVerdict>(
    () => resolveSetHint(setHint, hintVocabulary?.sets ?? [], hintVocabulary?.aliases ?? {}),
    [setHint, hintVocabulary],
  )

  /* The `datalist`'s entries: the alias codes the owner types, then TCGplayer's own names.
     Concatenated HERE rather than in the store, so `hintVerdict` can still tell them apart
     (an alias resolves to another hint; a name resolves to itself). */
  const hintSuggestions = useMemo<string[]>(
    () =>
      hintVocabulary === undefined
        ? []
        : [...Object.keys(hintVocabulary.aliases), ...hintVocabulary.sets.map((row) => row.name)],
    [hintVocabulary],
  )

  /** Flagging, in `--accent`'s "the system is unsure" job. A hint that names no set is not
   *  an error — nothing is refused and the capture is unaffected — so it is drawn at text
   *  weight, never as a halt. `ambiguous` joins it: `match_sets` returns both as misses. */
  const hintAlert = hintVerdict.state === 'unmatched' || hintVerdict.state === 'ambiguous'

  
  const boxQuery = boxEntry.trim()

  /* SUBSTRING OVER THE NUMBER AND THE NAME, and the two are not two modes. `9` keeps 9, 19,
   * 95 and 99 exactly as it always did; `com` keeps every box whose name carries it; `box 3`
   * keeps "common box 3". Case-folded on the name side only, because nobody narrows with a
   * shift key and a box number has no case to fold. */
  const boxMatchesAll = useMemo(() => {
    if (boxQuery === '') return boxOptions
    const folded = boxQuery.toLowerCase()
    return boxOptions.filter(
      (option) =>
        String(option.box).includes(boxQuery) ||
        (option.name ?? '').toLowerCase().includes(folded),
    )
  }, [boxOptions, boxQuery])

  const boxMatchTotal = boxMatchesAll.length

  /* AN EXACT MATCH LEADS, because it is what the operator typed and it is what Enter takes.
   * Exact on the NUMBER as a whole string, or on the NAME folded and trimmed — the same
   * comparison `store/master.py:_check_name_free` refuses a duplicate by, so what this
   * screen treats as one box and what the store treats as one name cannot come apart. */
  const boxExact = useMemo(() => {
    if (boxQuery === '') return undefined
    const folded = boxQuery.toLowerCase()
    return boxOptions.find(
      (option) =>
        String(option.box) === boxQuery || (option.name ?? '').trim().toLowerCase() === folded,
    )
  }, [boxOptions, boxQuery])

  /* THE ROWS THAT DRAW. Nine of them, and the reason for the number is a HEIGHT budget
   * rather than a keyboard one: `OPTION_KEYS` carries twenty-five, but nothing in this field
   * rides a key at all (see the entry — digits are typing here), and boxes are the one
   * vocabulary on this screen that is unbounded. `boxMatchTotal` is the pre-cap count, so the
   * note can say how many did not draw.
   *
   * THE FIRST NINE, TYPED OR NOT, because `boxOptions` is already in the hand's order
   * (D-capture-setup-memory). This took the LAST nine with nothing typed until then — the
   * highest-numbered, standing in for "most recent" on the reasoning that boxes are allocated
   * upward. The list is now sorted by what this browser actually reached for, so the front of
   * it is the answer in both cases and the two branches collapse into one. */
  const boxRows = useMemo(() => {
    const shown = boxMatchesAll.slice(0, 9)
    if (boxExact === undefined) return shown
    const rest = shown.filter((option) => option.box !== boxExact.box)
    return [boxExact, ...rest].slice(0, 9)
  }, [boxMatchesAll, boxExact])

  /** The row Enter takes, hoisted so the meta and the handler read the same one thing. */
  const boxTop = boxRows.length > 0 ? boxRows[0] : undefined

  
  const boxOffer = useMemo(() => {
    if (boxQuery === '' || boxExact !== undefined) return null
    if (BOX_DIGITS.test(boxQuery)) {
      const value = Number(boxQuery)
      if (!Number.isSafeInteger(value) || value < 1) return null
      return { box: value, name: null as string | null }
    }
    return { box: null as number | null, name: boxQuery }
  }, [boxQuery, boxExact])

  /** One selection ends the opening: set the box, record the reach, drop the note, close, and
   *  hand focus back so C and U are live again the moment a drawer is chosen.
   *
   *  THE REACH IS RECORDED HERE AND NOWHERE ELSE ON THIS SCREEN (D-capture-setup-memory).
   *  Picking a box is the act — it is a deliberate press, it happens once a sitting, and it is
   *  the moment the operator's attention moves to that drawer. Two things that might look like
   *  candidates are deliberately not:
   *
   *  A CAPTURE IS NOT ONE, and that is a cost argument as much as a semantic one. It fires once
   *  per card at a measured 623 ms cadence, so touching here would put a `localStorage`
   *  read-modify-write on the feeder's hot path — hundreds of times a box — to re-record a fact
   *  that has not changed since the pick that preceded every one of them.
   *
   *  A RESTORED BOX IS NOT ONE EITHER, for `BoxBrowse.tsx`'s stated reason: a page load is not
   *  an opening. The restore carries the box the operator last PICKED, and that pick already
   *  wrote its stamp; touching again on every mount would let a screen left open overnight
   *  outrank a box somebody actually reached for this morning. */
  const chooseBox = useCallback(
    (value: number) => {
      setBox(value)
      setRecency(touchBox(value))
      setBoxNote(null)
      setRestoreNote(null)
      closeField()
      blurActive()
    },
    [closeField],
  )

  
  useEffect(() => {
    if (openField !== null && openField !== 'box') return
    let live = true
    void (async () => {
      try {
        const answer = await getBoxes()
        if (!live) return
        setBoxRecords(answer.boxes)
        setBoxesSeen(true)
      } catch {
        // see above: the field degrades to numbers, which is what it had before. `boxesSeen`
        // stays false on purpose — a restored box must never be judged against a list that
        // did not arrive.
      }
    })()
    return () => {
      live = false
    }
  }, [openField])

  /* A RESTORED BOX IS CHECKED AGAINST THE STORE, ONCE, AND FAILS SOFTLY
     (D-capture-setup-memory).

     PHOTOGRAPHING INTO THE WRONG DRAWER IS THE EXPENSIVE FAILURE ON THIS SCREEN, and the
     setup now outlives the browser, so the gap between "the box I last picked" and "a box that
     still exists and still takes cards" is a gap that can be days wide. Between two sittings a
     box can be sealed (D20), deleted (D34's panel), or deleted and its number handed to a
     different physical drawer by `next_box_number`'s lowest-free allocation. The first two are
     refused at the shutter anyway; the THIRD is not refused anywhere, because box 7 exists and
     takes cards — it is simply not the box the operator thinks they are looking at.

     SO THE RESTORE FALLS BACK TO NO SELECTION, NEVER TO A GUESS, and it says which box it let
     go of and why. The field opens with focus in it, which is the same state `Pick a box` puts
     the operator in, so the remedy is the press they were going to make anyway.

     IT WAITS FOR `boxesSeen` AND NOT FOR A NON-EMPTY LIST. `boxRecords` starts `[]`, and `[]`
     is also what a store with no boxes answers — judging on emptiness would clear a perfectly
     good restored box every time the fetch was merely slow, which on a cold capture server is
     every time. `boxesSeen` is set only where the answer actually arrived.

     IT RUNS ONCE. `restoredBoxRef` is spent on the first answer — nulled before the verdict,
     so the good path spends it too — because the operator may deliberately re-pick a box this
     effect just cleared, or pick a sealed one to see the refusal, and an ungated version would
     take it straight back off them. What is being judged is the RESTORE, which happens on mount
     and never again. */
  const restoredBoxRef = useRef<number | null>(restored.box)
  useEffect(() => {
    const wanted = restoredBoxRef.current
    if (wanted === null || !boxesSeen) return
    restoredBoxRef.current = null
    const found = boxRecords.find((record) => record.box === wanted)
    if (found !== undefined && found.state !== 'closed') return
    setBox(null)
    setRestoreNote(
      found === undefined
        ? 'The box this browser was last set to is not in the store any more, so nothing is ' +
            'selected. Pick the drawer in front of you.'
        : `${captureBoxLabel(found.box, found.name)} has been sealed since you last captured ` +
            'into it, so nothing is selected. Pick another drawer.',
    )
    setOpenField('box')
  }, [boxesSeen, boxRecords])

  
  
  const createOfferedBox = useCallback(async () => {
    if (boxBusy) return
    if (boxOffer === null) {
      // Only reachable from an entry that is neither a box nor a name: `0`, or twenty
      // digits. The sentence says what a box is rather than what was wrong with the entry,
      // because both rejected shapes are things a person would call a number.
      setBoxNote('A box number is a whole number, 1 or higher. A name can be anything else.')
      return
    }
    setBoxBusy(true)
    setBoxNote(null)
    try {
      const row = await createBox(
        boxOffer.box === null ? { name: boxOffer.name ?? '' } : { box: boxOffer.box },
      )
      // Folded in rather than re-fetched: the answer IS the row `GET /boxes` would return
      // (`_box_row` renders all three routes), so a round trip would buy nothing and would
      // put a second await between the press and the box being current.
      setBoxRecords((prev) => [...prev.filter((known) => known.box !== row.box), row])
      chooseBox(row.box)
    } catch (error) {
      setBoxNote(
        error instanceof ServerError
          ? `${error.message} (${error.code})`
          : 'The box could not be created. Check the capture server is running.',
      )
    } finally {
      setBoxBusy(false)
    }
  }, [boxBusy, boxOffer, chooseBox])

  /** ONE PRESS PUTS THE SETUP BACK TO NOTHING CHOSEN (D-capture-setup-memory).
   *
   *  THE OWNER ASKED FOR IT IN FOUR WORDS: *"a quick clear all settings button"*. Quick is a
   *  requirement, so there is no confirmation dialog: the press clears, the screen visibly goes
   *  back to its empty state, and a receipt toast carries the way back. That is the shape D28
   *  settled for the review answer — act, receipt, undo — and it is the right one here for the
   *  same reason: a confirmation ahead of a reversible act buys nothing and costs a press every
   *  single time.
   *
   *  IT CLEARS CHOICES ABOUT CARDS, AND LEAVES THE RIG ALONE. Box, game, set hint, rarity,
   *  finish and product are things the operator decided about the stack in front of them, and
   *  the next stack is a different decision. The camera and the rotation are not decisions about
   *  cards at all — they are which piece of hardware is plugged in and which way it is mounted
   *  (D13), they are the same tomorrow as today, and `useCamera.ts` owns them. Clearing those
   *  would mean re-picking a 4K capture card to start a run that needs none of it re-picked, so
   *  the control says on its face what it leaves behind rather than surprising anybody.
   *
   *  NOTHING IN THE STORE IS TOUCHED AND THE CONTROL IS BUILT TO SAY SO. No route is called,
   *  no card moves, and the copy names the store explicitly — `docs/DESIGN.md`'s register
   *  reserves danger styling for destructive acts, and this is the opposite of one. A control
   *  that could be misread as deleting cards, on the screen where cards are created, is worth
   *  a sentence.
   *
   *  THE GAME GOES TO THE REGISTRY'S DEFAULT, NOT TO NULL, and that is what "nothing chosen"
   *  means for this one field. A fresh browser does not sit on no game: `loadGames` puts it on
   *  `registry.default` and the operator changes it if they want something else. Clearing to
   *  null would leave the screen drawing *"Waiting for the game list from the server"* — the
   *  blocked reason for a registry that has not arrived — which would be a sentence that is
   *  simply untrue, about a fetch that finished minutes ago. */
  const clearSetup = useCallback(() => {
    const before: CaptureSetup = { box, game, setHint, finish, rarityClaim, product }
    setBox(null)
    setGame(registry?.default ?? null)
    setSetHint('')
    setFinish([])
    setRarityClaim([])
    setProduct(null)
    setBoxNote(null)
    setRestoreNote(null)
    closeField()
    blurActive()
    /* FORGOTTEN OUTRIGHT RATHER THAN OVERWRITTEN WITH NOTHING. The persist effect below will
       write the cleared setup back on the next render anyway; removing the key first is what
       makes the clear true even if this tab is closed before that effect runs. */
    forgetCaptureSetup()
    toast({
      kind: 'receipt',
      icon: 'refresh',
      title: 'Setup cleared.',
      /* WHAT IS *NOT* AFFECTED, because what IS affected is already on screen — every row
         went back to its empty state as the toast appeared. A receipt that recited the six
         fields ran to four lines in the stack and said nothing the operator could not see. */
      body: 'The camera, the rotation and everything in the store are untouched.',
      action: {
        label: 'Undo',
        onPress: () => {
          setBox(before.box)
          setGame(before.game)
          setSetHint(before.setHint)
          setFinish([...before.finish])
          setRarityClaim([...before.rarityClaim])
          setProduct(before.product)
        },
      },
    })
  }, [box, game, setHint, finish, rarityClaim, product, registry, closeField])

  /* WHAT ENTER DOES, which is a POLICY and not a control: take the top row if there is one,
     and otherwise make what the offer names. That ordering is what keeps typing `com` from
     making a junk box when `common box 3` is right there — and it is exactly why the offer
     row must not route through here. */
  const takeBoxEntry = useCallback(async () => {
    if (boxBusy) return
    const top = boxTop
    if (top !== undefined) {
      if (top.sealed) {
        setBoxNote(
          `${captureBoxLabel(top.box, top.name)} is sealed and takes no more cards. Open it ` +
            `on the Inventory screen, or pick another.`,
        )
        return
      }
      chooseBox(top.box)
      return
    }
    await createOfferedBox()
  }, [boxBusy, boxTop, chooseBox, createOfferedBox])

  /* The rarity list, whole and in the game's own stack order. Never capped: the vocabulary
   * is fixed per game (`pipeline/games.py`) and every member must stay claimable — and since
   * 2026-08-24 every member is claimable BY KEY as well, because `OPTION_KEYS` runs past the
   * digits. This comment described a filter that no longer exists and a nine-chip cap that
   * no longer binds; both were the same stale sentence, and Pokemon's last four rarities
   * were what it was quietly costing. */
  const visibleRarities = useMemo(() => gameEntry?.rarities ?? [], [gameEntry])

  
  const fieldPick = useCallback(
    (nth: number) => {
      if (nth < 0) return
      if (openField === 'rarity') {
        const name = visibleRarities[nth]
        if (name !== undefined) toggleRarity(name)
      } else if (openField === 'game') {
        const entry = (registry?.games ?? [])[nth]
        if (entry !== undefined) {
          pickGame(entry.key)
          closeField()
        }
      } else if (openField === 'product') {
        const entry = (registry?.products ?? [])[nth]
        if (entry !== undefined) {
          // Re-pressing the claimed product takes it back out, exactly as the finish and
          // rarity cells do. Getting back to NO CLAIM has to be reachable by the same key
          // that made the claim — otherwise the only way out of a wrong product is a page
          // reload, on the screen the operator spends hours in.
          setProduct((current) => (current === entry.key ? null : entry.key))
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
        else if (nth === 2) switchTrigger('cadence')
        else return
        closeField()
      }
    },
    [
      openField,
      visibleRarities,
      toggleRarity,
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
  /* A LAYOUT EFFECT, SO THE LISTENER IS NEVER A RENDER BEHIND THE SCREEN (D128). `openField` is a
     dependency here and `fieldPick` closes over it, so every open or close re-registers this
     handler — and a passive effect does that after paint. In the task between the two, the track
     is drawn open while the attached closure still holds `openField === null`: Escape sees no
     field to close and returns, a digit picks from nothing. A press dispatched there is not
     queued, it is answered by the wrong render. `capture-claims.spec.ts` retries its `F` for the
     first-mount version of this and lost its Escape to this one twice on the Ubuntu runner.
     Inside the commit, before paint, the handler the screen shows is the handler that is on. */
  useLayoutEffect(() => {
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

      const nth = OPTION_INDEX.get(key)
      if (nth !== undefined) {
        event.preventDefault()
        fieldPick(nth)
        return
      }

    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [openField, gameEntry, toggleField, fieldPick])

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

  
  const undoStack = useMemo<UndoTarget[]>(() => {
    if (box === null) return []

    // The server's own newest for this box: the high-water mark, minus one. Zero for a box
    // it has never heard of, which is the same thing as empty for the comparison below.
    const serverNewest = nextForBox === undefined ? 0 : nextForBox - 1

    const mine = shots.filter((shot) => shot.card.box === box)
    const newest = mine[mine.length - 1]

    
    if (newest === undefined || serverNewest > newest.card.index) {
      if (serverNewest < 1) return []
      return [{ box, index: serverNewest, label: null }]
    }

    return mine
      .slice(-UNDO_DEPTH)
      .reverse()
      .map((shot) => ({ box: shot.card.box, index: shot.card.index, label: shot.card.label }))
  }, [box, nextForBox, shots])

  /* WHAT ONE PRESS OF `U` DELETES IS `undoStack[0]`, and there is deliberately no binding
   * for it any more. There used to be an `undoTarget`, and every guard on this screen read
   * it; now the depth is the only thing that varies and `undoBack` takes it as an argument,
   * so a second name for "the top of the stack" would be a second thing to keep in step
   * with the first. `doUndo` is the nullary call the trigger seam still needs.
   */

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
          // C10, and the omission rule is the other two's exactly: no claim sends no key,
          // and the sidecar stays a record of claims actually made. What is NOT here is a
          // default — an unclaimed code card reaches the Codes screen as unclaimed and is
          // refused by both channel lanes, which is the loud outcome. Writing `booster`
          // here would be the quiet one.
          product: product ?? undefined,
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
        setFlash((prev) => prev + 1)
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
    //
    // `product` WAS MISSING FROM THIS LIST AND IT SENT THE PREVIOUS STACK'S CLAIM. Found by
    // `react-hooks/exhaustive-deps` the day it was switched on, in code that had been merged
    // hours earlier. The claim is read at `product: product ?? undefined` above; the callback
    // is memoised on this array; and picking a product changes NONE of the other eight, so
    // the memoised closure kept whatever `product` held when it was last built. First stack
    // of a session that sends `null` is the loud outcome the comment at the call site is
    // counting on — an unclaimed code card is refused by both channel lanes. The SECOND stack
    // is the quiet one: it carries stack one's product, on real cards, and nothing downstream
    // can tell. That is precisely the failure the call site says it declined to create by not
    // writing a `booster` default, arriving by the other door.
    //
    // It belongs here for the same reason `finish` and `rarityClaim` do, and it costs what
    // they cost: the identity moves when the operator makes a claim, which is an act, not a
    // render. The seam re-arms on a keypress the operator made and not on a paint.
  }, [box, camera, finish, gameEntry, halt, product, rarityClaim, rememberCaptureId, setHint])

  
  const undoBack = useCallback(
    async (depth: number) => {
      if (busyRef.current) return
      const plan = undoStack.slice(0, Math.max(0, depth))
      if (plan.length === 0) return
      busyRef.current = true
      setBusy(true)
      setUndoNote(null)
      let did = 0
      let failure: unknown = null
      try {
        for (const target of plan) {
          try {
            /* The response is discarded on purpose. Its `deleted` is the store's own key —
             * "3/7" — and that is not a thing the operator has ever seen on this screen or
             * anywhere else; `types.ts` says as much where it defines the field ("Not a
             * label and not a SKU"). What goes on screen is the rendered position that was
             * under the control a moment ago, which is the same string the server sent when
             * the card was captured. */
            await undoCapture(target.box, target.index)
          } catch (err) {
            // STOP, do not carry on down the plan. The next card is only undoable because
            // this one was going to be gone, so continuing would aim at a card that is no
            // longer the newest and buy a second refusal — or, worse, be right for the
            // wrong reason.
            failure = err
            break
          }
          did += 1
          setShots((prev) =>
            prev.filter(
              (shot) => !(shot.card.box === target.box && shot.card.index === target.index),
            ),
          )
          setNextIndex((prev) => ({ ...prev, [String(target.box)]: target.index }))
          setRevision((prev) => prev + 1)
          // Whatever the replay note said is about a card that may be the one just deleted,
          // and a stale sentence about a position that no longer exists is worse than none.
          setReplayed(null)
        }

        const reached = plan[Math.max(0, did - 1)]
        if (failure === null) {
          // "Undo capture" produced "Undone" — docs/DESIGN.md's copy rule that an action
          // keeps its name through the flow. The count rides beside it rather than inside
          // it, so the one-card press reads exactly as it always did.
          setUndoNote({
            done: true,
            text: 'Undone',
            position: reached === undefined ? null : positionText(reached),
            code: null,
            did,
            want: plan.length,
          })
        } else {
          /* Deliberately not a halt. Spec 5.5 stops the run when a card may have gone past
           * unrecorded; a refused undo changed nothing at all, and the refusal names the
           * position that IS undoable. That is information beside the control, not a
           * stopped run.
           *
           * A PARTIAL WALK IS REPORTED AS ONE. `did` cards really are gone and the rest are
           * not, and both halves leave the list either way — so the count is the only thing
           * left that says where the operator actually is. */
          setUndoNote({
            done: false,
            position: did === 0 || reached === undefined ? null : positionText(reached),
            did,
            want: plan.length,
            ...describe(failure),
          })
        }
      } finally {
        busyRef.current = false
        setBusy(false)
      }
    },
    [undoStack],
  )

  /** One card, which is what `U` and the trigger seam mean by undo. Kept as its own
   *  function so the trigger's ref keeps pointing at a nullary call and D10's "undo stays
   *  manual forever" reads the same in the wiring below as it always did. */
  const doUndo = useCallback(async () => {
    await undoBack(1)
  }, [undoBack])

  
  const sectionBusyRef = useRef(false)
  const doSection = useCallback(async () => {
    if (box === null || sectionBusyRef.current) return
    sectionBusyRef.current = true
    setSectionBusy(true)
    setSectionNote(null)
    try {
      const record = await openSection(box)
      setBoxRecords((prev) => {
        const rest = prev.filter((entry) => entry.box !== record.box)
        return [...rest, record].sort((left, right) => left.box - right.box)
      })
      const spans = record.sections_detail
      /* `?? null` because `noUncheckedIndexedAccess` is on and is right to be: a record
       * that came back with no spans at all is a box the server could not render a layout
       * for, and the receipt then says the act's name with no detail rather than
       * `Section undefined`. */
      const opened = spans[spans.length - 1] ?? null
      setSectionNote({
        done: true,
        // The act's own name, kept through the flow (docs/DESIGN.md's copy rule), with what
        // it produced beside it. `from card N` and not `at card N`: the number is where the
        // section STARTS, and the next card is the first one in it.
        text: 'New section',
        place: opened === null ? null : `Section ${opened.section} · from card ${opened.start}`,
        code: null,
      })
    } catch (err) {
      setSectionNote({ done: false, place: null, ...describe(err) })
    } finally {
      sectionBusyRef.current = false
      setSectionBusy(false)
    }
  }, [box])

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
    // through the ref, so a fresh recording per arm needs no re-memoisation. `motionControls`
    // is filled in by the armed machine and nulled on teardown, which is what makes the
    // Re-baseline control render only while there is a machine to ask.
    () =>
      motionTrigger(
        camera.videoRef,
        setMotionDiag,
        DEFAULT_PARAMS,
        (t, d, dBase, luma, event, cells) => traceRef.current?.record(t, d, dBase, luma, event, cells),
        motionControls,
      ),
    [camera.videoRef],
  )
  /* Trigger 2 (D130): the same sampler, the same signal machine underneath, and a fire
   * scheduled on the feeder's own beat instead of on a settle the feeder never allows. Same
   * seam, same ref for its controls — `pinPeriod` is the one control the settle machine does
   * not have, and the Rig panel offers it only while this trigger is the one armed. */
  const beatTrigger = useMemo(
    () =>
      cadenceTrigger(
        camera.videoRef,
        setMotionDiag,
        DEFAULT_CADENCE,
        (t, d, dBase, luma, event, cells) => traceRef.current?.record(t, d, dBase, luma, event, cells),
        motionControls as RefObject<CadenceControls | null>,
      ),
    [camera.videoRef],
  )
  const captureTrigger =
    triggerMode === 'motion' ? machineTrigger : triggerMode === 'cadence' ? beatTrigger : keyTrigger
  const undoTrigger = useMemo(() => manualTrigger(UNDO_KEY), [])
  /* On the same primitive as the shutter and the undo, and never on the motion seam. A
   * divider is a physical act somebody performs with their hands; there is nothing for a
   * machine to detect and nothing it could be right about. `manualTrigger` is also what
   * makes a held `s` one divider rather than a run of them, and what keeps the letter from
   * firing while it is being typed into the set hint. */
  const sectionTrigger = useMemo(() => manualTrigger(SECTION_KEY), [])

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
      if (triggerMode !== 'manual') {
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
  const fireSectionRef = useRef<() => void>(() => {})
  useEffect(() => {
    fireUndoRef.current = () => void doUndo()
  }, [doUndo])
  useEffect(() => {
    fireSectionRef.current = () => void doSection()
  }, [doSection])
  useEffect(() => captureTrigger.start(() => fireCaptureRef.current()), [captureTrigger])
  useEffect(() => undoTrigger.start(() => fireUndoRef.current()), [undoTrigger])
  useEffect(() => sectionTrigger.start(() => fireSectionRef.current()), [sectionTrigger])

  
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

  
  const traceFrames = traceRef.current?.frameCount ?? 0

  
  const liveMediaClass = `capture-media capture-media-turn${camera.rotation}`

  
  /* EVERY reason a capture is blocked, not just the first one that happens to have a button.
   * A cause with a one-press way out carries it on its own row; a cause without one — the
   * game list, or a game with no TCGplayer export — is written out in the same list rather
   * than being replaced by the ones that can be pressed. Before this the shortcuts rendered
   * INSTEAD of the sentence, so an unverified game behind a closed camera said only "Open
   * the camera" and the operator never learned the cards could not join. */
  type Blocker = {
    key: string
    icon: IconName
    tone: 'plain' | 'warn'
    text: string
    fix: { label: string; icon: IconName; onPress: () => void } | null
  }

  const blockers: Blocker[] = []
  if (halt !== null) {
    /* Alone, and nothing else is worth pressing until the run is resumed. "Above" is right in
     * both layouts: the halt renders before the stage, so the resume control is up the page
     * from this line — pointing the operator the wrong way costs the seconds a stopped run
     * has least of. */
    blockers.push({
      key: 'halt',
      icon: 'alert',
      tone: 'warn',
      text: 'Captures are paused. Resume them above.',
      fix: null,
    })
  } else {
    if (!camera.started) {
      /* `started` false is nobody has asked — an ordinary beginning to a session, not a
       * fault, and the only one of the camera's three states that belongs here. `missing`
       * and `error` stay out: CameraPicker prints both, verbatim, a few pixels up. */
      blockers.push({
        key: 'camera',
        icon: 'camera',
        tone: 'plain',
        text: 'Open the camera before capturing.',
        fix: { label: 'Open the camera', icon: 'camera', onPress: camera.retry },
      })
    } else if (!camera.ready) {
      /* STARTED BUT NOT READY — asked for, and not delivering frames: a device that vanished,
       * a permission withdrawn, a stream that failed to negotiate. `canCapture` requires
       * `ready`, so the shutter is off in this state, and until now this list said NOTHING
       * about it: a disabled shutter with no stated cause, which is the exact failure the
       * "state every cause" ruling exists to end. The fault's own text is printed by the
       * stage and the Camera row; what belongs here is why the shutter will not fire, and
       * the same one press that reopens it. */
      blockers.push({
        key: 'camera-fault',
        icon: 'alert',
        tone: 'warn',
        text: 'The camera is open but sending no frames. Reopen it before capturing.',
        fix: { label: 'Reopen the camera', icon: 'refresh', onPress: camera.retry },
      })
    }
    if (box === null) {
      blockers.push({
        key: 'box',
        icon: 'box',
        tone: 'plain',
        text: 'Pick a box, or type a new one, before capturing.',
        fix: { label: 'Pick a box', icon: 'box', onPress: () => toggleField('box') },
      })
    }
    if (gameEntry === null) {
      /* NOT "pick a game" — there is nothing to pick from yet, and telling the operator to do
       * something the screen cannot offer is worse than saying nothing. Which of the two
       * sentences depends on whether the fetch failed or is simply outstanding, and only the
       * failure is a warning. */
      blockers.push(
        registryNote === null
          ? {
              key: 'game',
              icon: 'layers',
              tone: 'plain',
              text: 'Waiting for the game list from the server.',
              fix: null,
            }
          : {
              key: 'game',
              icon: 'layers',
              tone: 'warn',
              text:
                'The game list did not load, so there is nothing to capture as. Ask again ' +
                'under Rig.',
              fix: null,
            },
      )
    } else if (gameEntry.unverified) {
      /* D22's refusal, in the operator's terms rather than the server's. It names the game,
       * says what is missing, and says what would fix it. The file the rarities are authored
       * in (`pipeline/games.py`) is a fact for the person at the repo, not the one at the
       * lens, so it stays out of the sentence. */
      blockers.push({
        key: 'unverified',
        icon: 'layers',
        tone: 'warn',
        text:
          `${gameEntry.display} has no TCGplayer export yet, so a card captured as one could ` +
          'never be identified, priced or listed. Pick another game, or add its export and ' +
          'author its rarities first.',
        fix: null,
      })
    }
  }

  /* ---- what the rebuilt screen derives for itself, from state the plumbing already owns ---- */

  const boxName = box === null ? null : (boxRecords.find((record) => record.box === box)?.name ?? null)

  const cameraLabel = (() => {
    if (camera.deviceId === null) return null
    const chosen = camera.devices.find((device) => device.deviceId === camera.deviceId)
    return chosen === undefined || chosen.label === '' ? 'Camera' : chosen.label
  })()

  const cameraFault = camera.missing || camera.error !== null

  const phase: MotionPhase | null =
    triggerMode !== 'manual' && motionDiag !== null ? motionDiag.phase : null

  /* The beat, when the cadence trigger is the one armed; null under the other two. */
  const beat = triggerMode === 'cadence' && motionDiag !== null ? (motionDiag.beat ?? null) : null

  /* The stage lamp: what the feed is doing, in one pill. */
  const lamp: { tone: PillTone; icon: IconName; text: string } = !camera.started
    ? { tone: 'default', icon: 'camera', text: 'Camera off' }
    : cameraFault
      ? { tone: 'danger', icon: 'alert', text: 'Camera fault' }
      : !camera.ready
        ? camera.deviceId === null
          ? { tone: 'warn', icon: 'camera', text: 'Pick a camera' }
          : { tone: 'warn', icon: 'refresh', text: 'Connecting' }
        : { tone: 'live', icon: 'dot', text: 'Live' }

  /* The trigger's state, beside it. Manual mode is one word — its key rides on the shutter,
   * the one keycap on this stage; motion mode is the machine's own phase, which is the most
   * icon-shaped state in the product. */
  const mode: { tone: PillTone; icon: IconName; text: string } =
    triggerMode === 'manual'
      ? { tone: 'accent', icon: 'keyboard', text: 'Manual' }
      : motionDiag === null
        ? { tone: 'warn', icon: 'eye', text: 'Armed · no signal' }
        : !motionDiag.hasBaseline
          ? { tone: 'warn', icon: 'eye', text: 'Baseline pending' }
          : beat === 'waiting'
            ? { tone: 'ok', icon: 'clock', text: 'Waiting for the first card' }
            : beat === 'seeded'
              ? { tone: 'accent', icon: 'clock', text: `On the seed · ${motionDiag.periodMs ?? 0} ms` }
              : beat === 'locked'
                ? { tone: 'live', icon: 'clock', text: `On the beat · ${motionDiag.periodMs ?? 0} ms` }
                : beat === 'idle'
                  ? { tone: 'warn', icon: 'clock', text: 'Feeder stopped' }
          : phase === 'moving'
            ? { tone: 'live', icon: 'zap', text: 'Moving' }
            : phase === 'settling'
              ? { tone: 'accent', icon: 'clock', text: 'Settling' }
              : { tone: 'ok', icon: 'eye', text: 'Watching' }

  /* The presence meter: how far the scene is from the session's baseline against the floor
   * it has to clear. Drawn as a bar with a tick at the floor, so "is there a card" is a
   * glance rather than two decimals. */
  const presence =
    triggerMode !== 'manual' && motionDiag !== null && motionDiag.hasBaseline
      ? {
          value: motionDiag.dBase,
          floor: motionDiag.presenceFloor,
          pct: Math.max(
            0,
            Math.min(100, (motionDiag.dBase / Math.max(motionDiag.presenceFloor * 2, 1)) * 100),
          ),
        }
      : null

  /* Busy is WORKING, not disabled: the shutter keeps its fill and shows a spinner for the
   * encode and the POST, and `busyRef` inside `doCapture` is what refuses a second fire. */
  const shutterDisabled = !canCapture && !busy

  const swallowedTotal = swallowed.busy + swallowed.noBox + swallowed.notReady + swallowed.held

  /** WHETHER THERE IS ANYTHING TO CLEAR, which is what disables the control rather than hiding
   *  it (D-capture-setup-memory). A control that appears and disappears with the state it acts
   *  on makes the rail's height move under the operator's hand, and D118 forbids exactly that.
   *
   *  THE GAME IS COMPARED AGAINST THE REGISTRY'S DEFAULT, not against null, because that is
   *  what the clear writes — so a screen sitting on the default with no other claim reads as
   *  nothing chosen, which is what it is. Before the registry lands there is no default to
   *  compare with, and a null game is then genuinely unchosen. */
  const setupChosen =
    box !== null ||
    setHint.trim() !== '' ||
    finish.length > 0 ||
    rarityClaim.length > 0 ||
    product !== null ||
    (game !== null && registry !== null && game !== registry.default)

  /* The stage foot's word for the drawer: the name, or the number where there is no name
     (D-capture-setup-memory). This read `Box 3 · RB Epics` and carried the number twice on one
     screen, since the row above it opened with `Box 3` too. */
  const boxSentence = box === null ? 'No box' : captureBoxLabel(box, boxName)

  /* The store's next index for the box, named as the index it is. `#N` is reserved for the
   * counted card number every other screen draws (D58); a high-water mark is not one, and a
   * person moving between screens should never have to guess which `#` they are reading. */
  const boxNextText = boxIsEmpty ? 'Empty' : `next index ${nextForBox ?? '?'}`

  const gameSentence =
    gameEntry === null ? (registryNote === null ? 'Loading…' : 'Unavailable') : gameEntry.display

  const rarityText =
    gameEntry === null || rarityClaim.length === 0
      ? null
      : rarityClaim.length <= 2
        ? rarityClaim.join(' · ')
        : `${rarityClaim.length} of ${gameEntry.rarities.length} claimed`

  return (
    <main className="capture bn-page" data-mode={triggerMode} data-live={camera.ready ? 'true' : 'false'}>
      {/* Announces every record written, for anyone not looking at the screen. */}
      <div className="bn-sr" aria-live="polite">
        {last === undefined ? '' : `Recorded ${last.card.label}`}
      </div>

      {/* THE HALT (spec 5.5): full width and first. A stopped run, the one number that
          matters, and the one thing to press. The server's own sentence and its code are
          kept verbatim behind a disclosure. */}
      {halt === null ? null : (
        <section className="capture-halt" role="alert" ref={haltRef}>
          <div className="capture-halt-main">
            <span className="capture-halt-glyph" aria-hidden="true">
              <Icon name="alert" size={18} />
            </span>
            <div className="capture-halt-text">
              <h2 className="capture-halt-title">
                {halt.where === 'camera'
                  ? 'Captures are paused — no frame came from the camera.'
                  : 'Captures are paused — the card was not recorded.'}
              </h2>
              <p className="capture-halt-message">
                {halt.where === 'camera'
                  ? 'Set aside the card at the lens and check the camera feed before you resume.'
                  : 'Leave the card at the lens and capture it again after you resume — if it ' +
                    'was already recorded, the app will say so and give it no second position.'}
              </p>
              {triggerMode !== 'manual' && swallowed.halted > 0 ? (
                <p className="capture-halt-message capture-halt-count">
                  <span className="capture-inline-count">{swallowed.halted}</span>{' '}
                  {swallowed.halted === 1 ? 'card' : 'cards'} may have passed the lens unrecorded
                  while captures were paused. Set them aside and re-feed them after you resume.
                </p>
              ) : null}
              {triggerMode !== 'manual' && halt.where === 'server' ? (
                <p className="capture-halt-message">
                  After you resume, capture the held card with the button yourself — the
                  machine will not re-present a card it has already fired on.
                </p>
              ) : null}
            </div>
            <Button
              variant="primary"
              size="lg"
              icon="play"
              className="capture-resume"
              onClick={() => {
                setHalt(null)
                setSwallowed((prev) => ({ ...prev, halted: 0 }))
                void loadStatus()
              }}
            >
              Resume captures
            </Button>
          </div>
          <details className="capture-halt-details">
            <summary>
              <Icon name="chevronRight" size={14} />
              What the server said
            </summary>
            <p className="capture-halt-message capture-halt-server">{halt.text}</p>
            {halt.code === null ? null : <p className="capture-halt-code">{halt.code}</p>}
            <p className="capture-halt-message capture-halt-last">
              {last === undefined ? (
                'Nothing has been recorded in this session.'
              ) : (
                <>
                  Last recorded:{' '}
                  <span className="capture-inline-label">
                    <PositionLabel label={last.card.label} flow="run" />
                  </span>
                </>
              )}
            </p>
          </details>
        </section>
      )}

      {/* A capture that outlived the page (D27). Not rendered under a halt, which says it
          louder. */}
      {halt !== null || !heldAcrossReload ? null : (
        <section className="capture-carried" role="status">
          <Notice tone="warn" title="A capture from before this page reloaded was never confirmed.">
            Put that same card back at the lens and capture it — if the server did record it, it
            will say so and give it no second position. Do not feed the next card first.
          </Notice>
        </section>
      )}

      {/* THE HEAD: the screen's name and the run's odometer, in the kit's register. The feed
          lamp and the box sentence are the stage's, 60px lower, and are not drawn twice. */}
      <header className="capture-head">
        <div className="capture-head-text">
          <span className="bn-eyebrow">Workflow</span>
          <h1 className="capture-title">
            <Icon name="camera" size={20} />
            Capture
          </h1>
        </div>
        <div className="capture-odo" aria-label="This run">
          <Stat value={runCount === null ? '0' : String(runCount.shots)} label="captured" />
          <span className="capture-odo-rule" aria-hidden="true" />
          <Stat value={box === null ? '—' : String(nextForBox ?? 1)} label="next index" />
          <span className="capture-odo-rule" aria-hidden="true" />
          <Stat
            value={runCount === null ? '—' : `${runCount.low}–${runCount.high}`}
            label="index span"
          />
          {runCount === null ? null : runCount.gaps === 0 && runCount.ids === runCount.shots ? (
            <Pill tone="ok" icon="check" className="capture-odo-verdict">
              no gaps
            </Pill>
          ) : (
            <Pill tone="danger" icon="alert" className="capture-odo-verdict">
              {runCount.gaps === 0 ? '' : `${runCount.gaps} missing`}
              {runCount.gaps !== 0 && runCount.ids !== runCount.shots ? ' · ' : ''}
              {runCount.ids === runCount.shots ? '' : `${runCount.ids} ids of ${runCount.shots}`}
            </Pill>
          )}
        </div>
      </header>

      <div className="capture-shell">
        {/* ============ THE VIEWFINDER: the hero, on a dark stage in either theme ============ */}
        <section className="capture-stage" aria-label="Viewfinder">
          {/* The stage head: the feed and the trigger as lamps, and the presence meter while a
              machine is judging. A real row rather than an overlay, so nothing sits on the
              card. */}
          <div className="capture-stage-head">
            <div className="capture-lamps">
              <Pill tone={lamp.tone} icon={lamp.icon} className={lamp.tone === 'live' ? 'capture-lamp is-live' : 'capture-lamp'}>
                {lamp.text}
              </Pill>
              <Pill tone={mode.tone} icon={mode.icon} className="capture-lamp capture-lamp-mode">
                {mode.text}
              </Pill>
            </div>
            {presence === null ? null : (
              <div
                className={presence.value >= presence.floor ? 'capture-meter is-present' : 'capture-meter'}
                role="img"
                aria-label={`presence ${presence.value.toFixed(1)}, floor ${presence.floor.toFixed(1)}`}
              >
                <span className="capture-meter-label">presence</span>
                <span className="capture-meter-bar">
                  <span className="capture-meter-fill" style={{ width: `${presence.pct}%` }} />
                  <span className="capture-meter-tick" />
                </span>
                <span className="capture-meter-val">{presence.value.toFixed(1)}</span>
              </div>
            )}
          </div>

          <div className="capture-viewfinder">
            <div className="capture-viewport">
              <div className="capture-frame capture-frame-live" data-phase={phase ?? triggerMode}>
                {/* muted and playsInline are required for autoplay to start at all. No
                    facingMode anywhere — the Cam Link presents the rig camera as a plain UVC
                    webcam. This is the first `.capture-media` in the DOM and must stay so. */}
                <video className={liveMediaClass} ref={camera.videoRef} autoPlay playsInline muted />
                <span className="capture-corner capture-corner-tl" aria-hidden="true" />
                <span className="capture-corner capture-corner-tr" aria-hidden="true" />
                <span className="capture-corner capture-corner-bl" aria-hidden="true" />
                <span className="capture-corner capture-corner-br" aria-hidden="true" />
                {flash > 0 ? <span key={flash} className="bn-flash" aria-hidden="true" /> : null}
                {phase === 'settling' ? (
                  <svg
                    key={motionDiag?.fires ?? 0}
                    className="capture-ring"
                    viewBox="0 0 48 48"
                    aria-hidden="true"
                    style={{ '--cap-settle-ms': `${SETTLE_MS}ms` } as CSSProperties}
                  >
                    <circle className="capture-ring-track" cx="24" cy="24" r="20" />
                    <circle className="capture-ring-fill" cx="24" cy="24" r="20" />
                  </svg>
                ) : null}

                {camera.ready ? null : (
                  <div className="capture-frame-note">
                    {!camera.started ? (
                      <>
                        <span className="capture-frame-glyph" aria-hidden="true">
                          <Icon name="camera" size={26} />
                        </span>
                        <p className="capture-frame-title">The camera is not open</p>
                        <p className="capture-frame-body">
                          Nothing on this screen reaches for it until you ask.
                        </p>
                        <Button variant="primary" icon="camera" onClick={camera.retry}>
                          Open the camera
                        </Button>
                      </>
                    ) : cameraFault ? (
                      <>
                        <span className="capture-frame-glyph is-danger" aria-hidden="true">
                          <Icon name="alert" size={26} />
                        </span>
                        <p className="capture-frame-title">Camera fault</p>
                        <p className="capture-frame-body">
                          {camera.error ??
                            'The remembered camera is not connected. Check the Cam Link and that the camera is awake.'}
                        </p>
                        <Button icon="refresh" onClick={camera.retry}>
                          Reopen the camera
                        </Button>
                      </>
                    ) : camera.deviceId === null ? (
                      <>
                        <span className="capture-frame-glyph" aria-hidden="true">
                          <Icon name="camera" size={26} />
                        </span>
                        <p className="capture-frame-title">Pick a camera</p>
                        <p className="capture-frame-body">
                          None is remembered for this rig. Choose one under Rig, or press V.
                        </p>
                      </>
                    ) : (
                      <>
                        <span className="capture-frame-spinner" aria-hidden="true" />
                        <p className="capture-frame-title">Waiting for frames.</p>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* A run of empty-stand verdicts has exactly one likely cause and one remedy. */}
            {triggerMode !== 'manual' && (motionDiag?.noCardRun ?? 0) >= 3 ? (
              <div className="capture-stage-warn" role="alert">
                <Icon name="alert" size={16} />
                <p className="capture-refused">
                  {motionDiag?.noCardRun} settles in a row read as an empty stand. If cards are
                  going past the lens, the baseline was taken with something on the stand — clear
                  it and re-baseline. Those cards were not photographed.
                </p>
                <Button size="sm" icon="refresh" onClick={() => motionControls.current?.rebaseline()}>
                  Re-baseline
                </Button>
              </div>
            ) : null}
          </div>

          {/* The stage foot: where the next photograph goes, and how the run is doing. */}
          <div className="capture-stage-foot">
            <span className="capture-foot-box">
              <Icon name="box" size={14} />
              <span className="capture-foot-box-name">{boxSentence}</span>
              {box === null ? null : (
                <span className="capture-foot-next">next index {nextForBox ?? 1}</span>
              )}
            </span>
            {/* ============ TUNING: the machine's readout and instruments, off the surface ============ */}
            <details className="capture-tuning">
              <summary>
                <Icon name="settings" size={14} />
                <span className="capture-tuning-word">Tuning</span>
                <span className="capture-tuning-sum">
                  {triggerMode === 'manual'
                    ? ''
                    : motionDiag === null
                      ? 'armed · no frames yet'
                      : triggerMode === 'cadence'
                        ? `${motionDiag.beat ?? 'waiting'} · ${motionDiag.periodMs ?? 0} ms · ${motionDiag.fires} fires`
                        : `${motionDiag.phase} · ${motionDiag.fires} fires`}
                  {swallowedTotal > 0 ? ` · ${swallowedTotal} dropped` : ''}
                </span>
                <Icon name="chevronUp" size={13} className="capture-chev" />
              </summary>
              <div className="capture-tuning-body">
                {triggerMode === 'manual' ? (
                  <p className="capture-quiet">
                    Arm the motion or cadence trigger under Rig (T) and the machine's readout appears here.
                  </p>
                ) : motionDiag === null ? (
                  <p className="capture-quiet">
                    Motion is armed but no frame has reached it yet. Open a camera and the readout
                    appears here.
                  </p>
                ) : (
                  /* Every span is `name value` with one space — motion-live.spec.ts parses the row
                     by that shape, and every number here is one the machine actually decides on. */
                  <p className="capture-motion-hud">
                    <span>{motionDiag.phase}</span>
                    <span>d {motionDiag.d.toFixed(2)}</span>
                    <span>tlo {motionDiag.tLo.toFixed(2)}</span>
                    <span>thi {motionDiag.tHi.toFixed(2)}</span>
                    <span>typ {motionDiag.dTypical.toFixed(2)}</span>
                    <span>dbase {motionDiag.dBase.toFixed(2)}</span>
                    <span>floor {motionDiag.presenceFloor.toFixed(2)}</span>
                    {motionDiag.hasBaseline ? null : (
                      <span className="capture-refused">baseline pending</span>
                    )}
                    <span>fires {motionDiag.fires}</span>
                    <span>same {motionDiag.suppressedUnchanged}</span>
                    <span>empty {motionDiag.suppressedNoCard}</span>
                    <span>stall {motionDiag.stalled}</span>
                    {/* D131: how often the ratchet was overruled by the rest quantile. Non-zero
                        on a bright lamp is the machine working; non-zero on a dim one is worth a
                        trace. */}
                    <span>escape {motionDiag.escapes}</span>
                    {triggerMode !== 'cadence' ? null : (
                      /* The beat's own instruments (D130). `beat` is a word and the live spec's
                         parser skips it by shape; the rest are `name value` like every span. */
                      <>
                        <span>beat {motionDiag.beat ?? 'waiting'}</span>
                        <span>period {motionDiag.periodMs ?? 0}</span>
                        <span>lock {(motionDiag.beatCoeff ?? 0).toFixed(2)}</span>
                        <span>blind {motionDiag.blindFires ?? 0}</span>
                      </>
                    )}
                    {swallowedTotal === 0 ? null : (
                      <span className="capture-refused">dropped {swallowedTotal}</span>
                    )}
                  </p>
                )}
                <div className="capture-tuning-actions">
                  {triggerMode !== 'manual' && motionDiag !== null ? (
                    <Button size="sm" icon="refresh" onClick={() => motionControls.current?.rebaseline()}>
                      Re-baseline · stand must be empty
                    </Button>
                  ) : null}
                  {traceFrames > 0 ? (
                    <Button size="sm" icon="download" onClick={() => traceRef.current?.download()}>
                      Save trace · {traceFrames} frames
                    </Button>
                  ) : null}
                </div>
              </div>
            </details>
          </div>
        </section>

        {/* ============ THE LAST CAPTURE: the bytes the Mac stored, and its receipt ============ */}
        <aside className="capture-last" aria-label="Last capture" data-has-last={last === undefined ? 'false' : 'true'}>
          <div className="capture-panel-head">
            <span className="bn-label">Last capture</span>
            {last === undefined ? null : last.card.created ? (
              <Pill key={last.card.key} tone="ok" icon="check" className="bn-anim-pop capture-written">
                Written
              </Pill>
            ) : (
              <Pill key={last.card.key} tone="warn" icon="history" className="bn-anim-pop capture-written">
                Already recorded
              </Pill>
            )}
          </div>
          <div className="capture-last-viewport">
          <div className="capture-frame capture-frame-last">
            {last === undefined ? (
              <div className="capture-frame-note capture-frame-note-last">
                <span className="capture-frame-glyph" aria-hidden="true">
                  <Icon name="image" size={24} />
                </span>
                <p className="capture-frame-title">Your first capture lands here</p>
                <p className="capture-frame-body">
                  Big enough to catch a blur or a finger before the card goes back in the box.
                </p>
              </div>
            ) : (
              <img
                key={last.card.key}
                className="capture-media"
                src={photoSrc(last.card.box, last.card.index, revision)}
                alt={`Capture at ${last.card.label}`}
              />
            )}
          </div>
          {last === undefined ? null : (
            <div className="capture-said">
              <p className="capture-label">
                <PositionLabel label={last.card.label} />
              </p>
              <p className="capture-said-meta">
                <Pill icon="layers">{last.game.display}</Pill>
                {typeof last.setHint === 'string' && last.setHint !== '' ? (
                  <Pill mono>{last.setHint}</Pill>
                ) : (
                  <Pill>No set hint</Pill>
                )}
                <Pill>{last.finish.length === 0 ? 'No claim' : last.finish.map(finishLabel).join(' · ')}</Pill>
                {last.card.new_box ? (
                  <Pill tone="accent" className="capture-flag">
                    New box
                  </Pill>
                ) : null}
                {last.card.created ? null : (
                  <Pill tone="warn" className="capture-flag">
                    Already recorded
                  </Pill>
                )}
              </p>

              {/* The note on the last capture, after the fact — never before the shutter. Its
                  own form, so Enter saves and never reaches the shutter. */}
              <form
                className="capture-inline"
                onSubmit={(event) => {
                  event.preventDefault()
                  void saveNote(last, noteDraft)
                  blurActive()
                }}
              >
                <div className="bn-input-wrap capture-note-wrap">
                  <Icon name="list" size={14} />
                  <input
                    className="bn-input capture-text capture-note"
                    type="text"
                    placeholder={last.game.catalogued ? 'Add a note to this card' : 'What is this card?'}
                    aria-label={`Note on ${last.card.label}`}
                    value={noteDraft}
                    onChange={(event) => setNoteDraft(event.target.value)}
                  />
                  <Button
                    type="submit"
                    size="sm"
                    variant="ghost"
                    icon="check"
                    iconOnly
                    className="capture-note-save"
                    disabled={noteBusy}
                  >
                    Save note
                  </Button>
                </div>
              </form>
              {last.game.catalogued ? null : (
                <p className="capture-quiet">
                  This card gets no identification call, so this note is the only thing it can be
                  found by later. A name and a game is enough.
                </p>
              )}
              {noteSaved === null ? null : (
                <p className={noteSaved.done ? 'capture-quiet capture-note-ok' : 'capture-refused'}>
                  {noteSaved.done ? <Icon name="check" size={13} /> : <Icon name="alert" size={13} />}
                  {noteSaved.text}
                  {noteSaved.code === null ? null : <span className="capture-halt-code"> {noteSaved.code}</span>}
                </p>
              )}
            </div>
          )}
          </div>
        </aside>

        {/* ============ THE RUN: the box, the shutter, the divider ============ */}
        <section className="capture-card capture-card-run" aria-label="Run">
          <p className="bn-label capture-card-label">Run</p>

          {openField === 'box' ? (
            <OpenField
              k="B"
              label="Box"
              icon="box"
              size="lg"
              meta={`${boxes.length} ${boxes.length === 1 ? 'box' : 'boxes'}`}
              onClose={closeField}
            >
              <div className="capture-entry">
                <div className="capture-entrybox bn-input-wrap">
                  <Icon name="search" size={14} />
                  <input
                    ref={boxEntryRef}
                    className="capture-filter bn-input"
                    type="text"
                    aria-label="Find a box by number or name, or type a new one"
                    placeholder="Number or name"
                    value={boxEntry}
                    disabled={boxBusy}
                    onChange={(event) => {
                      setBoxEntry(event.target.value)
                      setBoxNote(null)
                    }}
                    onKeyDown={(event) => {
                      if (event.key !== 'Enter') return
                      event.preventDefault()
                      void takeBoxEntry()
                    }}
                  />
                  <span className="capture-entrymeta">
                    {boxBusy
                      ? 'Adding…'
                      : boxTop !== undefined
                        ? boxTop.sealed
                          ? 'Sealed'
                          : `Next index ${boxTop.next ?? '?'}`
                        : boxOffer !== null
                          ? 'New box'
                          : ''}
                  </span>
                </div>
              </div>
              <div className="capture-opts">
                {boxRows.map((option) => (
                  <Opt
                    key={option.box}
                    on={option.box === box}
                    /* THE NAME LEADS AND THE NUMBER FOLLOWS IT, which is the reverse of what
                       this drew until 2026-09-11 (D-capture-setup-memory). The number STAYS
                       here, unlike everywhere else on the screen, because this is the one place
                       it is doing a job: the entry above searches number and name together, and
                       a row that hid the number would answer a search for `9` with nine rows
                       that do not visibly contain a 9. An unnamed box has only the number, so
                       `captureBoxLabel` puts it in the name's place and the suffix drops. */
                    name={captureBoxLabel(option.box, option.name)}
                    sfx={option.name === null ? null : ` Box ${option.box}`}
                    trail={option.sealed ? 'Sealed' : `next index ${option.next ?? '?'}`}
                    trailWord={option.sealed}
                    onPick={() => {
                      if (option.sealed) {
                        setBoxNote(
                          `${captureBoxLabel(option.box, option.name)} is sealed and takes no ` +
                            `more cards. Open it on the Inventory screen, or pick another.`,
                        )
                        return
                      }
                      chooseBox(option.box)
                    }}
                  />
                ))}
                {boxOffer === null ? null : (
                  <Opt
                    on={false}
                    name={boxOffer.box === null ? (boxOffer.name ?? '') : `Box ${boxOffer.box}`}
                    trail="New"
                    trailWord
                    onPick={() => void createOfferedBox()}
                  />
                )}
              </div>
              <p className="capture-opennote">
                {boxMatchTotal > boxRows.length
                  ? `${boxMatchTotal} boxes match; ${boxRows.length} shown. Narrow it, or press Enter to take the top row.`
                  : 'Enter takes the top row. Anything new is created by name.'}
              </p>
              {boxNote === null ? null : <p className="capture-refused">{boxNote}</p>}
              {restoreNote === null ? null : (
                <p className="capture-refused">
                  <Icon name="alert" size={13} /> {restoreNote}
                </p>
              )}
            </OpenField>
          ) : (
            <Row
              k="B"
              label="Box"
              icon="box"
              size="lg"
              right={
                box === null ? (
                  <span className="capture-box-val is-empty">
                    <strong>No box yet</strong>
                    <span>Pick one, or type a new name</span>
                  </span>
                ) : (
                  /* THE NAME IS THE HEADLINE AND THE NUMBER IS GONE (D-capture-setup-memory).
                     It read `Box 3` over `RB Epics · next index 41`, which made the operator
                     read past the number to reach the word they think in. `captureBoxLabel`
                     falls back to `Box 3` for a drawer nobody has named, so an unnamed box is
                     still identifiable and no placeholder is invented (D56). */
                  <span className="capture-box-val">
                    <strong>{captureBoxLabel(box, boxName)}</strong>
                    <span>{boxNextText}</span>
                  </span>
                )
              }
              onToggle={() => toggleField('box')}
            />
          )}

          <div className="capture-controls">
            <Button
              variant="primary"
              size="xl"
              block
              icon="camera"
              className="capture-shutter"
              onClick={() => void doCapture()}
              disabled={shutterDisabled}
              busy={busy}
              /* In motion mode the C key is genuinely disarmed, so the keycap goes; the
                 button itself stays live in both modes as an override. */
              kbd={triggerMode === 'manual' ? CAPTURE_KEY_LABEL : undefined}
            >
              Capture card
            </Button>

            {/* One block: the sentence is the whole truth and the shortcut rides on the
                cause it fixes, so a cause with no button is read rather than replaced. */}
            {blockers.length === 0 ? null : (
              <div className="capture-block" role="group" aria-label="Before you can capture">
                <span className="bn-label capture-block-word">Before you can capture</span>
                <ul className="capture-block-list">
                  {blockers.map((blocker) => (
                    <li key={blocker.key} className="capture-block-row" data-tone={blocker.tone}>
                      <Icon name={blocker.icon} size={14} />
                      <span className="capture-block-say">{blocker.text}</span>
                      {blocker.fix === null ? null : (
                        <Button
                          size="sm"
                          icon={blocker.fix.icon}
                          className="capture-block-fix"
                          onClick={blocker.fix.onPress}
                        >
                          {blocker.fix.label}
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {replayed === null ? null : (
              <Notice tone="warn" className="capture-replayed">
                Already recorded at{' '}
                <span className="capture-inline-label">
                  <PositionLabel label={replayed} flow="run" />
                </span>
                . Move on.
              </Notice>
            )}
          </div>

          <div className="capture-section">
            <Button
              icon="divider"
              kbd={SECTION_KEY_LABEL}
              block
              onClick={() => void doSection()}
              disabled={box === null || sectionBusy}
              busy={sectionBusy}
            >
              New section
            </Button>
            {sectionNote === null ? null : (
              <p className={sectionNote.done ? 'capture-quiet capture-note-ok' : 'capture-refused'}>
                {sectionNote.done ? <Icon name="check" size={13} /> : <Icon name="alert" size={13} />}
                {sectionNote.text}
                {sectionNote.place === null ? null : (
                  <>
                    {' '}
                    <span className="capture-inline-label">{sectionNote.place}</span>
                  </>
                )}
                {sectionNote.code === null ? null : (
                  <span className="capture-halt-code"> {sectionNote.code}</span>
                )}
              </p>
            )}
          </div>

          {/* The way onward: once the box holds cards, the run hands it to the pipeline. Runs
              reads only `?run=` today, so the box is picked there. */}
          {box !== null && !boxIsEmpty ? (
            <div className="capture-onward">
              <Button
                icon="zap"
                iconRight="arrowRight"
                block
                onClick={() => (window.location.hash = '#/runs')}
              >
                {/* THE NAME HERE TOO (D-capture-setup-memory), even though the destination
                    draws `Box 4 · Mixed Singles`. This button is read on THIS screen, by
                    somebody who has just finished feeding a drawer, and it names the drawer
                    they fed — `#/runs` composing the pair when they get there is that screen's
                    job and is right for its own reason (`boxLabel` in `runScope.ts`). */}
                Identify {captureBoxLabel(box, boxName)} on Runs
              </Button>
            </div>
          ) : null}
        </section>

        {/* ============ RECENT: what undo can reach, as a filmstrip ============ */}
        <footer className="capture-undo capture-film" aria-label="Recent captures">
          <div className="capture-film-head">
            <p className="capture-field-name bn-label">
              Recent
              {undoStack.length > 1 ? (
                <span className="capture-undo-depth">{undoStack.length} recent</span>
              ) : null}
            </p>
            {undoStack.length === 0 ? null : (
              <p className="capture-film-hint" title="A thumbnail undoes that card and everything captured after it">
                <Kbd>{UNDO_KEY_LABEL}</Kbd> undoes the newest
              </p>
            )}
          </div>

          {undoStack.length === 0 ? (
            <p className="capture-quiet capture-film-empty">
              <Icon name="film" size={14} />
              {box === null
                ? 'Captures you can undo will appear here once a box is picked.'
                : 'Nothing in this box to undo yet.'}
            </p>
          ) : (
            <ul className="capture-undo-list">
              {undoStack.map((target, at) => (
                <li key={`${target.box}/${target.index}`} style={{ animationDelay: `${at * 30}ms` }}>
                  <button
                    type="button"
                    className="capture-undo-row"
                    onClick={() => void undoBack(at + 1)}
                    disabled={busy}
                    data-undo={at === 0 ? 'Undo' : `Undo ${at + 1}`}
                    aria-label={
                      at === 0
                        ? `Undo the newest capture, ${positionText(target)}`
                        : `Undo ${at + 1} captures, back to ${positionText(target)}`
                    }
                  >
                    <img
                      className="capture-undo-thumb capture-undo-thumb-portrait"
                      src={photoSrc(target.box, target.index, revision)}
                      alt=""
                    />
                    <span className="capture-undo-pos">{undoFigure(target)}</span>
                    <span className={at === 0 ? 'capture-key is-newest' : 'capture-key'}>
                      {at === 0 ? UNDO_KEY_LABEL : at + 1}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {undoNote === null ? null : (
            <p className={undoNote.done ? 'capture-quiet capture-note-ok' : 'capture-refused'}>
              {undoNote.done ? <Icon name="undo" size={13} /> : <Icon name="alert" size={13} />}
              {undoNote.did !== undoNote.want ? (
                <span className="capture-undo-partial">
                  Undid {undoNote.did} of {undoNote.want}.{' '}
                </span>
              ) : null}
              {undoNote.text}
              {undoNote.done && undoNote.did > 1 ? ` ${undoNote.did} captures, back to` : null}
              {undoNote.position === null ? null : (
                <>
                  {' '}
                  <span className="capture-inline-label">
                    <PositionLabel label={undoNote.position} flow="run" />
                  </span>
                </>
              )}
              {undoNote.code === null ? null : (
                <span className="capture-halt-code"> {undoNote.code}</span>
              )}
            </p>
          )}
        </footer>

        {/* ============ THE STACK: claims set once per stack ============ */}
        <section className="capture-card capture-card-stack" aria-label="Stack claims">
          <p className="bn-label capture-card-label">Stack</p>

          {openField === 'set' ? (
            <OpenField k="H" label="Set hint" icon="tag" meta="Optional" onClose={closeField}>
              <form
                className="capture-entry"
                onSubmit={(event) => {
                  event.preventDefault()
                  if (hintVerdict.state === 'matched' && !hintVerdict.exact) {
                    setSetHint(hintVerdict.set)
                  }
                  closeField()
                  blurActive()
                }}
              >
                <div className="capture-entrybox bn-input-wrap">
                  <Icon name="tag" size={14} />
                  <input
                    ref={hintRef}
                    className="capture-filter bn-input"
                    type="text"
                    placeholder="sv09"
                    aria-label="Set hint"
                    list="capture-set-names"
                    value={setHint}
                    onChange={(event) => setSetHint(event.target.value)}
                  />
                  <datalist id="capture-set-names">
                    {hintSuggestions.map((name: string) => (
                      <option key={name} value={name} />
                    ))}
                  </datalist>
                  <span
                    className={
                      hintAlert ? 'capture-entrymeta capture-entrymeta-alert' : 'capture-entrymeta'
                    }
                  >
                    {hintMetaText(hintVerdict)}
                  </span>
                </div>
              </form>
              {hintVocabulary === undefined ? null : hintVocabulary.reason ? (
                <p className="capture-opennote">
                  {hintReason(hintVocabulary.reason, hintVocabulary.message)}. The hint is
                  stored exactly as typed.
                </p>
              ) : (
                <p className={hintAlert ? 'capture-opennote capture-note-alert' : 'capture-opennote'}>
                  {hintNoteText(hintVerdict, gameEntry?.display ?? 'this game')}
                </p>
              )}
            </OpenField>
          ) : (
            <Row
              k="H"
              label="Set hint"
              icon="tag"
              right={
                setHint.trim() === '' ? (
                  <span className="capture-val is-default">None</span>
                ) : (
                  <span className={hintAlert ? 'capture-val capture-val-alert' : 'capture-val'}>
                    <span className="bn-mono capture-val-name">{setHint.trim()}</span>
                    {hintAlert ? <em className="capture-sub">names no set</em> : null}
                  </span>
                )
              }
              onToggle={() => toggleField('set')}
            />
          )}

          {gameEntry !== null && gameEntry.rarities.length > 1 ? (
            openField === 'rarity' ? (
              <OpenField
                k="R"
                label="Rarity"
                icon="sparkles"
                meta={`${rarityClaim.length} of ${gameEntry.rarities.length} claimed`}
                onClose={closeField}
              >
                <div className="capture-opts">
                  {visibleRarities.map((name, position) => {
                    const [stem, sfx] = rarityNameParts(name)
                    return (
                      <Opt
                        key={name}
                        k={OPTION_KEYS[position]}
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
                icon="sparkles"
                right={
                  rarityText === null ? (
                    <span className="capture-val is-default">{NO_CLAIM_LABEL}</span>
                  ) : (
                    <span className="capture-val">
                      {rarityText}
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
                    </span>
                  )
                }
                onToggle={() => toggleField('rarity')}
              />
            )
          ) : null}

          {gameEntry !== null && gameEntry.finishes.length > 1 ? (
            openField === 'finish' ? (
              <OpenField
                k="F"
                label="Finish"
                icon="sun"
                meta={`${finish.length} of ${gameEntry.finishes.length} claimed`}
                onClose={closeField}
              >
                <Track
                  label="Finish"
                  cells={gameEntry.finishes.map((member) => ({
                    text: finishLabel(member),
                    on: finish.includes(member),
                    disabled: offeredFinishes !== null && !offeredFinishes.has(member),
                    onPick: () => toggleFinish(member),
                  }))}
                />
                {offeredFinishes === null ||
                gameEntry.finishes.every((member) => offeredFinishes.has(member)) ? null : (
                  <p className="capture-opennote">
                    {gameEntry.finishes
                      .filter((member) => !offeredFinishes.has(member))
                      .map(finishLabel)
                      .join(' · ')}{' '}
                    — not stocked under the claimed rarities
                  </p>
                )}
              </OpenField>
            ) : (
              <Row
                k="F"
                label="Finish"
                icon="sun"
                right={
                  finish.length === 0 ? (
                    <span className="capture-val is-default">{NO_CLAIM_LABEL}</span>
                  ) : (
                    <span className="capture-val">{finish.map(finishLabel).join(' · ')}</span>
                  )
                }
                onToggle={() => toggleField('finish')}
              />
            )
          ) : null}

          {registry !== null && game === registry.product_game ? (
            openField === 'product' ? (
              <OpenField
                k="P"
                label="Product"
                icon="package"
                meta="Pick one"
                onClose={closeField}
              >
                <div className="capture-opts">
                  {registry.products.map((entry, nth) => (
                    <Opt
                      key={entry.key}
                      k={OPTION_KEYS[nth]}
                      on={product === entry.key}
                      onPick={() =>
                        setProduct((current) => (current === entry.key ? null : entry.key))
                      }
                      name={entry.display}
                      trail={entry.premium ? 'Premium' : undefined}
                      trailWord
                    />
                  ))}
                </div>
                <p className="capture-opennote">
                  Which sealed product this stack came out of. Leave it unclaimed if you do not
                  know — an unclaimed code is counted on the Codes screen and refused by both
                  channel lanes, which is louder than a wrong guess.
                </p>
              </OpenField>
            ) : (
              <Row
                k="P"
                label="Product"
                icon="package"
                right={
                  product === null ? (
                    <span className="capture-val is-default">{NO_CLAIM_LABEL}</span>
                  ) : (
                    <span className="capture-val">
                      {registry.products.find((e) => e.key === product)?.display ?? product}
                    </span>
                  )
                }
                onToggle={() => toggleField('product')}
              />
            )
          ) : null}

          {statusNote === null ? null : (
            <div className="capture-servernote">
              <p className="capture-refused">{statusNote.text}</p>
              <Button size="sm" icon="refresh" onClick={() => void loadStatus()}>
                Ask again
              </Button>
            </div>
          )}
        </section>

        {/* ============ THE RIG: set once when the rig is set up, then read ============ */}
        <section className="capture-card capture-card-rig" aria-label="Rig">
          <p className="bn-label capture-card-label">Rig</p>

          {openField === 'game' ? (
            <OpenField k="G" label="Game" icon="layers" meta="Pick one" onClose={closeField}>
              <div className="capture-opts">
                {(registry?.games ?? []).map((entry, position) => (
                  <Opt
                    key={entry.key}
                    k={OPTION_KEYS[position]}
                    on={entry.key === game}
                    name={entry.display}
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
                  <p className="capture-refused">{registryNote.text}</p>
                  <Button size="sm" icon="refresh" onClick={() => void loadGames()}>
                    Ask again
                  </Button>
                </>
              )}
              {gameEntry === null ? null : gameEntry.unverified ? (
                <p className="capture-opennote" title="Rarities are authored in pipeline/games.py">
                  No TCGplayer export has been seen for {gameEntry.display}, so a card captured as
                  one could never be identified, priced or listed. Captures are held until an
                  export is in hand and its rarities are authored.
                </p>
              ) : !gameEntry.catalogued ? (
                <p className="capture-opennote">
                  {gameEntry.display} is captured and located like any other card and then stops:
                  no identification call, no join, no listing. A note under the last capture is
                  the only thing it can be found by later.
                </p>
              ) : gameEntry.prompt === PROMPT_UNWRITTEN ? (
                <p className="capture-opennote">
                  {gameEntry.display} has an export but no identification prompt yet, so these
                  cards will be captured and positioned now and identified later.
                </p>
              ) : null}
            </OpenField>
          ) : (
            <Row
              k="G"
              label="Game"
              icon="layers"
              right={
                gameEntry === null ? (
                  <span className="capture-val is-default">{gameSentence}</span>
                ) : (
                  <span className="capture-val">{gameEntry.display}</span>
                )
              }
              onToggle={() => toggleField('game')}
            />
          )}

          {openField === 'camera' ? (
            <OpenField
              k="V"
              label="Camera"
              icon="camera"
              meta={
                signal !== null ? (
                  <span className={underTarget ? 'capture-meta-alert' : undefined}>
                    {signal.width} × {signal.height}
                  </span>
                ) : !camera.started ? (
                  'Not open'
                ) : (
                  `${camera.devices.length} found`
                )
              }
              onClose={closeField}
            >
              {!camera.started ? (
                <>
                  <p className="capture-opennote">
                    The camera is not open yet. Nothing on this screen reaches for it until you
                    ask, so opening the app raises no permission prompt.
                  </p>
                  <Button variant="primary" size="sm" icon="camera" onClick={camera.retry}>
                    Open the camera
                  </Button>
                </>
              ) : (
                <>
                  <div className="capture-opts">
                    {camera.devices.map((device, position) => (
                      <Opt
                        key={device.deviceId}
                        k={OPTION_KEYS[position]}
                        on={device.deviceId === camera.deviceId}
                        name={device.label === '' ? `Camera ${position + 1}` : device.label}
                        onPick={() => camera.selectDevice(device.deviceId)}
                      />
                    ))}
                    {camera.devices.length === 0 ? (
                      <p className="capture-quiet">No cameras found.</p>
                    ) : null}
                  </div>
                  {camera.missing ? (
                    <p className="capture-refused">
                      The remembered camera is not connected. Check the Cam Link and that the
                      camera is awake, or pick a camera above. Nothing is open until you do.
                    </p>
                  ) : null}
                  {camera.error === null ? null : <p className="capture-refused">{camera.error}</p>}
                  {underTarget ? (
                    <p className="capture-refused">
                      This stream is below the {PIPELINE_LONG_EDGE}px the pipeline works from, so
                      every photo will be worse than the rig can produce. Check the camera is in
                      its clean-HDMI output mode and that nothing else is holding the capture card.
                    </p>
                  ) : null}
                  {camera.missing || camera.error !== null || underTarget ? (
                    <Button size="sm" icon="refresh" onClick={camera.retry}>
                      Reopen the camera
                    </Button>
                  ) : null}
                </>
              )}
            </OpenField>
          ) : (
            <Row
              k="V"
              label="Camera"
              icon="camera"
              right={
                !camera.started ? (
                  <span className="capture-val is-default">Not open</span>
                ) : cameraFault ? (
                  <span className="capture-val capture-val-alert">
                    <Icon name="alert" size={12} />
                    Fault
                  </span>
                ) : camera.deviceId === null ? (
                  <span className="capture-val capture-val-alert">
                    <Icon name="camera" size={12} />
                    Pick one
                  </span>
                ) : !camera.ready ? (
                  <span className="capture-val is-default">Connecting…</span>
                ) : (
                  <span className="capture-val">
                    <span className="capture-val-name">{cameraLabel ?? 'Camera'}</span>
                    {signal === null ? null : (
                      <em className={underTarget ? 'capture-sub capture-sub-alert' : 'capture-sub'}>
                        {signal.width}×{signal.height}
                      </em>
                    )}
                  </span>
                )
              }
              onToggle={() => toggleField('camera')}
            />
          )}

          {openField === 'rotation' ? (
            <OpenField k="O" label="Rotation" icon="rotate" meta="Pick one" onClose={closeField}>
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
              icon="rotate"
              right={<span className="capture-val bn-tnum">{camera.rotation}°</span>}
              onToggle={() => toggleField('rotation')}
            />
          )}

          {openField === 'trigger' ? (
            <OpenField
              k="T"
              label="Trigger"
              icon={triggerIcon(triggerMode)}
              meta={
                <>
                  {triggerMode === 'motion'
                    ? 'Motion · the machine fires it'
                    : triggerMode === 'cadence'
                      ? 'Cadence · settle first, beat as backstop'
                      : `Manual · ${CAPTURE_KEY_LABEL} fires it`}
                  <span className="bn-sr capture-trigger">{captureTrigger.name}</span>
                </>
              }
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
                  {
                    text: 'cadence',
                    on: triggerMode === 'cadence',
                    onPick: () => {
                      switchTrigger('cadence')
                    },
                  },
                ]}
              />
              {triggerMode !== 'cadence' ? null : (
                /* THE ONE CONTROL THE SETTLE MACHINE DOES NOT HAVE (D130). Empty means the
                   machine measures the beat itself, which is the default and what the trace
                   says it does well; a number holds the period there while the phase is still
                   measured. It stays inside the open field because a pin is a tuning act, not
                   a session claim, and the field is where the trigger is chosen. */
                <div className="capture-entrybox bn-input-wrap capture-period">
                  <Icon name="clock" size={14} />
                  <input
                    className="capture-filter bn-input"
                    type="number"
                    inputMode="numeric"
                    min={300}
                    max={2500}
                    step={10}
                    placeholder={`${motionDiag?.measuredMs ?? DEFAULT_CADENCE.periodSeedMs}`}
                    aria-label="Beat period in milliseconds"
                    value={periodPin}
                    onChange={(event) => {
                      const raw = event.target.value
                      setPeriodPin(raw)
                      const controls = motionControls.current
                      if (controls !== null && 'pinPeriod' in controls) {
                        const ms = raw.trim() === '' ? null : Number(raw)
                        controls.pinPeriod(ms !== null && Number.isFinite(ms) ? ms : null)
                      }
                    }}
                  />
                  <span className="capture-entrymeta">
                    {periodPin.trim() === ''
                      ? motionDiag?.measuredMs != null
                        ? `measured ${motionDiag.measuredMs} ms`
                        : `seed ${DEFAULT_CADENCE.periodSeedMs} ms until measured`
                      : 'ms · pinned'}
                  </span>
                </div>
              )}
              <p className="capture-opennote">
                {triggerMode === 'motion'
                  ? 'The machine fires the shutter when a card settles at the lens. Arming starts the run; it never survives a reload.'
                  : triggerMode === 'cadence'
                    ? 'The dual: a card that settles is photographed the moment it does, and a card that never does is photographed on the feeder\'s beat, measured from the motion itself. Leave the period blank to let it measure.'
                    : 'The shutter fires on C. Motion arms a machine that fires it when a card settles; Cadence arms one that fires on a feeder\'s beat.'}
              </p>
            </OpenField>
          ) : (
            <Row
              k="T"
              label="Trigger"
              icon={triggerIcon(triggerMode)}
              right={
                <span className={triggerMode === 'manual' ? 'capture-val' : 'capture-val is-armed'}>
                  {triggerMode === 'manual' ? 'Key' : triggerMode === 'motion' ? 'Motion' : 'Cadence'}
                  <em className="bn-sr capture-trigger">
                    {captureTrigger.name}
                  </em>
                </span>
              }
              onToggle={() => toggleField('trigger')}
            />
          )}

          {/* THE CLEAR, AT THE FOOT OF THE LAST PANEL IN THE RAIL (D-capture-setup-memory).
              It reaches all three panels — the box in Run, the four claims in Stack, the game
              here — so there is no panel it BELONGS to, and the foot of the column is where a
              control that ends a sitting reads as ending one. The head was the alternative and
              was refused: `.capture-head-text` is display:none under 767px, so the head is the
              odometer alone on a phone and a reset button would be crowding the one row that is
              already tight there.

              QUIET, NOT DANGER. It destroys nothing — `docs/DESIGN.md` reserves red for acts
              that do — and the sentence under it names the store explicitly, because this is
              the screen where cards are made and "clear" is a word that could be misread. */}
          <div className="capture-clear">
            <Button
              variant="quiet"
              size="sm"
              block
              icon="refresh"
              onClick={clearSetup}
              disabled={!setupChosen}
            >
              Clear the setup
            </Button>
            <p className="capture-opennote capture-clear-note">
              {setupChosen
                ? 'Puts the box, the game and every claim back to nothing chosen. The camera, the rotation and everything in the store are untouched.'
                : 'Nothing is chosen, so there is nothing to clear.'}
            </p>
          </div>
        </section>

      </div>
    </main>
  )
}
