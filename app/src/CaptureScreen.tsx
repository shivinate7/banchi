import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { PositionLabel } from './PositionLabel'
import type { ReactNode } from 'react'

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
import type { MotionControls, MotionDiagnostics } from './motion'
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

/* THE THIRD ACT ON THIS SCREEN, and the owner asked for it in exactly those terms on
 * 2026-08-29: "just like C is capture, I want S for Sectioning". It puts a divider in front
 * of the next card, at the moment the real one goes into the box.
 *
 * AN ACT, NOT A FIELD, WHICH IS WHY IT IS HERE AND NOT IN `FIELD_KEYS`. Every letter in that
 * table opens something to choose from and changes what the NEXT photograph will claim. This
 * one writes to the store on the press, like the shutter and the undo, and it is on the same
 * `manualTrigger` primitive they are — so auto-repeat, held modifiers and keys typed into an
 * input are decided once, in one module, rather than in a second listener here that would
 * have to be kept in step with it. A divider is a physical act; a held `s` is not eleven of
 * them.
 *
 * IT COST THE SET HINT ITS LETTER, and the swap is the owner's: the set hint is `h` now. The
 * screen had `s` on the field an operator opens a few times a run and needed it for the act
 * they perform at the box. `h` is not a worse mnemonic for a hint, and nothing else on this
 * screen had claimed it. */
const SECTION_KEY = 's'

/* HOW FAR BACK THE UNDO STACK GOES. The owner's number, 2026-08-29: "let's say the 10 most
 * recent captures that I can just click undo capture on from the sidebar".
 *
 * IT IS A DEPTH, NOT A HISTORY. Every row is a card this SESSION captured, newest first, and
 * pressing one walks the undo back through every card above it — because D10 allows undo to
 * reach the newest capture in a box and nothing else, and repeated undo is how it reaches
 * further. A row is therefore "undo this and everything after it", which is what an undo
 * stack means everywhere else, rather than "delete this one" — that operation exists
 * (D10 ruling 1's mid-box remove) and deliberately lives on `#/inventory`, because it slides
 * every higher card down one index and would renumber the very list it was pressed from.
 *
 * TEN IS A HEIGHT AS WELL AS A NUMBER. The list is capped and scrolls, and the heading says
 * how many it holds, so a capped list cannot read as a short one — `BoxOps`' section list,
 * same problem, same answer. */
const UNDO_DEPTH = 10

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
}

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
/* Why the set suggestions are missing, in the operator's terms (D65).
 *
 * THE SESSION ONE IS THE ONLY ACTIONABLE CASE AND IT NAMES THE FILE. The others are stated
 * plainly and no more: this is the rig's screen, the field still works, and a paragraph about
 * a cookie would be louder than the thing it describes. The raw code is kept on the end
 * because `docs/DESIGN.md` shows reason codes beside names — what you saw stays greppable. */
function hintReason(code: string | null): string {
  if (!code) return ''
  if (code === 'tcg_session_expired') return 'TCGplayer session expired — replace it in .env'
  if (code === 'tcg_cookie_missing') return 'no TCGplayer session — set one in .env'
  if (code === 'no_category') return 'no TCGplayer category for this game'
  return `set list unavailable (${code})`
}

/* WHAT THE HINT FIELD SAYS ABOUT WHAT IS IN IT (D65, amended 2026-08-31).
 *
 * THE FIELD ALWAYS HAD RULES AND NEVER DREW THEM. D65 gave the hint a vocabulary and a
 * `datalist`, and a `datalist` is a suggestion box: it offers the real set names and says
 * nothing at all about the string actually typed. So `Spiritforge` and `Spiritforged` look
 * identical at the rig, and they part company an hour of captures later at the fetch — one
 * scopes the export to that set, the other resolves to nothing and widens to the whole
 * category. The operator learns which they typed from a row count on a different screen.
 *
 * TWO REGISTERS, BECAUSE THE BOX FIELD BESIDE IT ALREADY HAS TWO. A terse meta pinned to
 * the right of the entry — `next 60`, `new box` — for the state, and a sentence under the
 * field for what that state means. This is that grammar applied to the one other free-text
 * field on the screen; nothing here is a new shape.
 *
 * NOTHING IN EITHER OF THEM REFUSES. Every string is still storable, `unmatched` included,
 * and the sentence says what happens to it rather than asking for a different one. D65's
 * reason stands: the rig does not stop for an autocomplete. */
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
  // C10's product claim. A scalar like `game` and `setHint`, not JSON like the claim above:
  // a stack came out of one sealed product, so there is nothing to flatten.
  product: 'pkmnscan.session.product',
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

/** Digits, a safe integer, 1 or higher — the Box entry's own rule exactly, and it has to be: the
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
/** The product claim as stored. A plain string, unlike the two set-valued claims above it:
 *  a stack came out of exactly one sealed product, so "two products at once" is not a state
 *  the operator can be in. Unvalidated here and checked against the registry when it lands,
 *  exactly as `readSessionGame` is. */
function readSessionProduct(): string | null {
  const raw = readSession(SESSION_KEYS.product)
  return raw && raw.trim() ? raw.trim() : null
}

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

/* THE OPTION ALPHABET — the keys an open field's rows ride, in order.
 *
 * It was `1`-`9` and nothing else, and Pokemon's thirteen rarities are what convicted that:
 * four rows drew no chip at all, so `Special Illustration Rare` through `Rainbow Rare` were
 * mouse-only on the screen whose whole keyboard argument is that a claim costs one press.
 * The owner's ruling, 2026-08-24: past nine, carry on with `0` and then the letters.
 *
 * IT IS NOT `a`-`z`, AND THE SKIPS ARE THE POINT. This screen has spent eleven letters:
 * `b h r f g v o t` are the fields, and `c u s` are the three acts — the shutter, the undo,
 * and the divider. A literal alphabet hands position 13 the key `c`, on the screen
 * that runs at a 623 ms feeder cadence, where `c` means take the photograph. That is not a
 * collision to settle by precedence: whichever way it settled, one of the two acts would
 * fire while the operator believed the other had, silently, one card at a time. So the
 * alphabet is every key this screen has NOT already spent, in order, and every existing key
 * keeps exactly the meaning it had — no shadowing, no mode, nothing reassigned.
 *
 * NOBODY COMPUTES IT. Every row draws its own key in its chip (`Opt`), so a gap at `b` and
 * `c` costs one glance to read, the same way the rotation value is printed in the sidebar
 * rather than remembered. That is what makes skipping cheaper than shadowing: the skip is
 * visible on screen and the shadow would not have been.
 *
 * Twenty-five keys (thirty-six less the eleven above), against a longest authored
 * vocabulary of thirteen (`pipeline/games.py`).
 * A field that ever out-grows this draws no chip past the end rather than a chip that does
 * nothing — `Opt`'s rule, kept, now at a bound no real vocabulary reaches. */
const RESERVED_KEYS: ReadonlySet<string> = new Set([
  ...Object.keys(FIELD_KEYS),
  CAPTURE_KEY,
  UNDO_KEY,
  SECTION_KEY,
])

/* `n` USED TO BE RESERVED HERE AND IS NOT ANY MORE, which widens this alphabet by one and
 * is the intended consequence rather than a side effect. It was `NEW_BOX_KEY`, the jump to
 * the Box field's second input — and that input no longer exists: the filter and the new-box
 * entry are one control now, so there is nothing to jump to. A key held back for a control
 * that was deleted is a key no row can ride for no reason anybody could still state.
 *
 * `s` THEN TOOK THE WIDTH BACK, 2026-08-29 — the divider act. The two cancel, so the option
 * rows are drawn on the same letters they were before either change: `0 a d e i…`. Worth
 * knowing when reading `app/tests/capture-claims.spec.ts`, which pins the tenth through
 * thirteenth rarities to `0 a d e` and stayed green through both. `h` is a field letter now
 * and sits after `e`, so it could only ever have moved a row past the thirteenth. */

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
 *  THE CHIP IS WHATEVER `OPTION_KEYS` PUTS AT THIS POSITION, and past the end of that
 *  alphabet there is no chip at all — drawn keyless rather than drawn with a key that does
 *  nothing, which is the one half of the old rule that survives.
 *
 *  The other half does not. This read "keyless past nine is deliberate, not a truncation",
 *  on the argument that digits are the only single keystrokes there are and one filter
 *  keystroke re-indexes the survivors into reach. Both premises had gone: the rarity field
 *  has no filter (owner, 2026-08-23) and letters are single keystrokes too, so what the
 *  paragraph actually defended was Pokemon's last four rarities being mouse-only. The owner
 *  ruled it out on 2026-08-24 and `OPTION_KEYS` carries the replacement. */
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
  const [boxNote, setBoxNote] = useState<string | null>(null)
  // Creating a box is now a REQUEST, where it used to be a local assignment: a name has to
  // reach the store before anything can be captured into it, and it can be refused
  // (`name_taken`). This gates the entry's Enter so a double press cannot post twice.
  const [boxBusy, setBoxBusy] = useState(false)
  const [setHint, setSetHint] = useState(readSessionSetHint)

  /* D65's whitelist: the real set names for the claimed game, offered in the hint field.
   *
   * WHY THE HINT NEEDED A VOCABULARY AT ALL. A hint typed free-hand is matched against
   * TCGplayer's set names later, and the two disagree — `OGN` is the community code for the
   * set TCGplayer calls `Origins`, and a hint that resolves to nothing widens the export to
   * every set in the category. Offering the real names makes the stored hint exact.
   *
   * LAZY, CACHED AND UNABLE TO FAIL LOUDLY. Loaded when the field is first opened rather than
   * at mount, because most sessions never touch it; kept per game; and a failure leaves the
   * list empty so the control is the plain text input it has always been. The rig does not
   * stop for an autocomplete. */
  const [tcgSets, setTcgSets] = useState<
    Record<
      string,
      { sets: SetOption[]; aliases: Record<string, string>; reason: string | null }
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
            },
          })),
        )
        .catch(() =>
          setTcgSets((prev) => ({
            ...prev,
            [forGame]: { sets: [], aliases: {}, reason: 'unreachable' },
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

  /* THE BOX ENTRY. One control where there were two — the filter and the `N` new-box field
   * — because they were one act wearing two shapes: both took digits, both ended with "this
   * is now the current box", and nothing separated them except which one held focus.
   *
   * It is FREE TEXT rather than digits, which is the half that makes a box findable by what
   * it is called. Digits search the number, letters search the name, and neither is a mode:
   * they are just what was typed.
   *
   * NOT RESTORED FROM `sessionStorage`, and that is the distinction D27's carve-out rests
   * on: a half-typed box entry is not a claim the operator has made. Restoring one would put
   * a value in the field that has never been submitted and does not agree with `box`. What
   * IS restored is the resolved box number, which is a claim.
   *
   * Cleared whenever the open field changes — an entry is an aid to one opening, and a
   * remembered one would re-narrow a list the operator cannot see the reason for. */
  const [boxEntry, setBoxEntry] = useState('')

  /* THE BOXES, AS THE REGISTRY KNOWS THEM — `GET /boxes`, not `/status`.
   *
   * `/status` carries `next_index` and nothing else, so this screen has never had a name to
   * draw and could not tell a sealed box from an open one. Both cost something real. The
   * name is the whole of what the owner asked for. The lid is a defect: D20 has
   * `allocate_capture` raise `BoxClosed` BEFORE it computes an index, so a sealed box could
   * be offered here and refuse at the shutter — a refusal mid-feed, which is the
   * rhythm-breaker this screen is built to avoid.
   *
   * `_box_row` already returns `box`, `name`, `state`, `next_index` and `fill`, so one route
   * serves the whole field and `/status` keeps every other job it has. Read on mount and
   * again whenever the field opens, which is rare — names change about as often as boxes do,
   * and this is O(cards) per box on the server. */
  const [boxRecords, setBoxRecords] = useState<BoxRecord[]>([])

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
  /* C10's product claim, and it behaves exactly like `game` above: session state, resent
   * with every capture, written to the record and the sidecar, correctable afterwards on the
   * card that got it wrong. `null` is NO CLAIM and is never defaulted to `booster` — being
   * right most of the time is precisely the problem, because the times it is wrong a $1.50
   * Pokemon Center ETB code leaves in a penny lot and nobody finds out. The Codes screen
   * counts unclaimed codes and refuses to put them in either lane for the same reason. */
  const [product, setProduct] = useState<string | null>(readSessionProduct)

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
  // `did` and `want` are 1 and 1 for the ordinary press and differ only for a walk-back that
  // stopped early — the one outcome the operator cannot see for themselves, because the
  // cards that went and the cards that did not both leave the list.
  const [undoNote, setUndoNote] = useState<
    (Note & { done: boolean; position: string | null; did: number; want: number }) | null
  >(null)
  const [revision, setRevision] = useState(0)

  /* THE LAST `S`, AS A RECEIPT — `undoNote`'s shape, for the same reason: a sentence beside
   * the control that produced it, which docs/DESIGN.md permits and a dialog is not. `place`
   * carries the section and its first card in the utility face, the way `position` does for
   * the undo, and is null on a refusal because the server's own sentence names the divider
   * that is in the way.
   *
   * ITS BUSY FLAG IS NOT `busy`, AND THAT IS DELIBERATE. `busy` gates the shutter; the note
   * editor above already keeps its own for the reason that applies here word for word — a
   * write that blocked the trigger would drop feeder cards while the operator was doing
   * something else. The cost is that a divider pressed in the same instant as a capture may
   * land on either side of that one card, which is a corner the operator is not in (a
   * divider goes in during a gap in feeding) and is one edit in the dividers editor if they
   * ever are. A dropped card is not recoverable at all. */
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

  /* The armed machine's own control surface — today only `rebaseline`. Null whenever motion
   * is not armed, which is exactly when the control below must not render. */
  const motionControls = useRef<MotionControls | null>(null)

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
    writeSession(SESSION_KEYS.product, product)
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

  /* ONE BOX, AS THIS FIELD NEEDS IT — the registry's name and lid, `/status`'s live index.
   *
   * Two sources rather than one, and each is authoritative over a different fact. The
   * registry read (`GET /boxes`) is the only place a NAME or a LID exists. `/status`'s
   * `next_index` is the fresher of the two after a capture, because `doCapture` advances it
   * locally on every write — so it wins on `next`, and it also adds any box whose first card
   * landed since the last registry read.
   *
   * Neither is dropped when the other is missing. A box the registry has never heard of but
   * that cards already name is a real box (`_box_row` renders exactly that case), and a box
   * created empty has no cards and so appears in the registry alone. */
  const boxOptions = useMemo(() => {
    const byNumber = new Map<number, BoxOption>()
    for (const record of boxRecords) {
      if (!Number.isInteger(record.box)) continue
      byNumber.set(record.box, {
        box: record.box,
        name: record.name,
        next: record.next_index,
        sealed: record.state === 'closed',
      })
    }
    for (const key of Object.keys(nextIndex)) {
      const value = Number(key)
      if (!Number.isInteger(value)) continue
      const known = byNumber.get(value)
      if (known === undefined) {
        byNumber.set(value, { box: value, name: null, next: nextIndex[key], sealed: false })
      } else {
        known.next = nextIndex[key]
      }
    }
    return [...byNumber.values()].sort((left, right) => left.box - right.box)
  }, [boxRecords, nextIndex])

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

  /* The two text entries, focused when their field opens. On the Box field that is what
   * makes "thirty boxes cost what three cost" true as typed: B, what you call it, Enter,
   * with no click in between. The cost is that a focused input eats the field letters (they
   * are typing) — Esc still closes from inside an input, deliberately, because it types
   * nothing and a trap that needs a mouse to leave is worse than an inconsistent key.
   *
   * There used to be a third, and losing it is the point. The Box field held a filter AND a
   * new-box entry, so the one thing that opened focused was never the one that created, and
   * `n` existed to jump between them. */
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

  /* WHAT THE BOX FILTER SHOWS. Substring on the box number — `9` keeps 9, 19, 95 and 99,
   * which is the mockup's own worked example — capped at nine rows, and the reason for the
   * number changed on 2026-08-24 without the number moving. It used to be BY CONSTRUCTION:
   * digits were the only keys there were. `OPTION_KEYS` now carries twenty-five, so the cap
   * is a HEIGHT budget and a scanning one instead: the column's measured worst case is the
   * rarity field's thirteen rows, and this is the one field whose vocabulary is unbounded
   * (boxes already number in the nineties). Nine rows plus a filter that re-indexes on every
   * keystroke is what that field has instead of a longer list. With no filter the
   * highest-numbered nine stand in for "most recent": the store's boxes are allocated
   * upward, recency is not a fact `/status` carries, and the top of the range is the end the
   * operator is working. `boxMatchTotal` is the pre-cap count, so the meta can say
   * `4 of 30 match` honestly while only nine draw. */
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
   * vocabulary on this screen that is unbounded. With nothing typed the highest-numbered
   * nine stand in for "most recent": boxes are allocated upward and recency is not a fact
   * either route carries. `boxMatchTotal` is the pre-cap count, so the note can say how many
   * did not draw. */
  const boxRows = useMemo(() => {
    const shown = boxQuery === '' ? boxMatchesAll.slice(-9) : boxMatchesAll.slice(0, 9)
    if (boxExact === undefined) return shown
    const rest = shown.filter((option) => option.box !== boxExact.box)
    return [boxExact, ...rest].slice(0, 9)
  }, [boxMatchesAll, boxExact, boxQuery])

  /** The row Enter takes, hoisted so the meta and the handler read the same one thing. */
  const boxTop = boxRows.length > 0 ? boxRows[0] : undefined

  /* WHAT WOULD BE CREATED, or null when the entry names something that already exists.
   *
   * DIGITS MEAN A NUMBER AND LETTERS MEAN A NAME, which is the whole of the rule. An
   * all-digit entry that matches no box exactly creates THAT NUMBER, unnamed — byte-for-byte
   * what the old `N` field did, so the path every box in this store was made by still works.
   * Anything else creates a box CALLED that, and the server takes the lowest free number
   * (`next_box_number`), because the owner's ask was to stop caring which one it is.
   *
   * A number that is not a box refuses rather than being offered: `'0'`, and a string of
   * twenty digits, are both things `Number` reads happily and neither is a drawer. */
  const boxOffer = useMemo(() => {
    if (boxQuery === '' || boxExact !== undefined) return null
    if (BOX_DIGITS.test(boxQuery)) {
      const value = Number(boxQuery)
      if (!Number.isSafeInteger(value) || value < 1) return null
      return { box: value, name: null as string | null }
    }
    return { box: null as number | null, name: boxQuery }
  }, [boxQuery, boxExact])

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

  /* THE REGISTRY READ. On mount, and again whenever the Box field opens.
   *
   * Not on the `/status` poll: `_box_row` is O(cards) per box on the server, and a name and
   * a lid change about as often as boxes are made. Re-read on open so a box named or sealed
   * from `#/inventory` on the other device shows up here without a reload — D13 puts one
   * truth on the Mac precisely so two screens cannot disagree about it.
   *
   * FAILS SILENTLY TO AN EMPTY LIST, deliberately. Every box that holds a card still comes
   * through `/status`, so a registry read that does not answer costs this field its names
   * and its lids and nothing else — the operator can still reach every box they could reach
   * before this route was read at all. A halt banner for a decoration would be worse. */
  useEffect(() => {
    if (openField !== null && openField !== 'box') return
    let live = true
    void (async () => {
      try {
        const answer = await getBoxes()
        if (live) setBoxRecords(answer.boxes)
      } catch {
        // see above: the field degrades to numbers, which is what it had before.
      }
    })()
    return () => {
      live = false
    }
  }, [openField])

  /* WHAT ENTER DOES, AND IT IS ONE SENTENCE: it takes the top row.
   *
   * The rule used to be that Enter took a LONE match and did nothing otherwise, which made
   * it a dead key on the common case and meant the operator had to hold the store's contents
   * in their head to know which. It was then going to be LITERAL — the digits you typed are
   * the box — and that is right for digits and unstateable for names: `mega` denotes no box
   * until one is called that.
   *
   * So the rule is stated over the SCREEN instead of over the draft. The top row is drawn
   * before it is taken, which answers the objection that killed lone-match — it was never
   * that partial matching is wrong, it was that you could not see what it would do.
   *
   * THE CREATION ROW IS LAST, so it is the top row only when nothing matched. Typing `com`
   * against an existing "common box 3" selects that box; it does not make a junk one. The
   * cost, named rather than designed away: creating "commons" while "commons A" exists needs
   * the creation row clicked, because Enter will take the incumbent.
   *
   * A SEALED BOX REFUSES HERE rather than being skipped over. D20 shuts a box against more
   * cards, and silently selecting a different one would be this screen answering a question
   * the operator did not ask. */
  /* MAKE THE BOX THE OFFER NAMES. Its own function, and separating it from `takeBoxEntry`
     below is a fix rather than a tidy: the creation ROW used to call `takeBoxEntry`, which
     takes the top match FIRST, so clicking a row that read `com · new` while `common box 3`
     matched selected box 3 and created nothing. A control that says `new` and quietly
     switches the capture target to an existing drawer is the worst version of this screen's
     one dangerous mistake — every photograph after it lands in the wrong box, at 623 ms a
     card, and nothing on screen contradicts it because the field has closed.

     `boxOffer` is non-null whenever the entry is not an EXACT match, so the offer row and a
     partial match are on screen together routinely; the two paths were never interchangeable
     and only Enter's policy made them look it. */
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
          `Box ${top.box}${top.name === null ? '' : ` · ${top.name}`} is sealed and takes no ` +
            `more cards. Open it on the Inventory screen, or pick another.`,
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

  /* AN OPTION KEY ACTS ONLY INSIDE AN OPEN FIELD, and always on what is currently VISIBLE —
   * the re-indexing rule. In the multi-select it toggles; in a single-select list or a track
   * it picks and closes; on the box list it picks the indexed match. Track cells draw no key
   * chips (the mockup's call — four cells in 306px have no room for chips that would mostly
   * be blank) but the keys work there all the same, because "options ride the alphabet" is
   * the design's one sentence about choosing and an exception per control shape is a rule
   * nobody can hold. A key into a disabled cell does nothing, exactly like a click.
   *
   * `nth` IS A POSITION, NOT A KEY. The handler resolves the press through `OPTION_INDEX`
   * and passes the index, so nothing below has to know that position 11 is `a` — which is
   * what let the alphabet grow past the digits without touching one branch of this switch. */
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

  /* WHAT UNDO CAN REACH, NEWEST FIRST — up to `UNDO_DEPTH` of them. Row 0 is what `U` and
   * every trigger fire aim at; row N is reached by undoing through rows 0..N.
   *
   * ONLY THIS BOX. The route deletes the newest card in the box it is given, and repeated
   * undo walks backwards one card per call — which is the whole mechanism a deeper row uses.
   *
   * INDICES ARE NOT WALKED DOWNWARD, AND THAT IS THE TRAP THIS AVOIDS. `serverNewest - 1` is
   * not the next undoable card: sold cards leave permanent gaps (D10) and a mid-box remove
   * closes one, so the second-newest index in a box is whatever record actually sits there.
   * The only thing that knows is the store — and, for this session, the shots themselves. So
   * the stack is built from real records and never from arithmetic on a high-water mark.
   */
  const undoStack = useMemo<UndoTarget[]>(() => {
    if (box === null) return []

    // The server's own newest for this box: the high-water mark, minus one. Zero for a box
    // it has never heard of, which is the same thing as empty for the comparison below.
    const serverNewest = nextForBox === undefined ? 0 : nextForBox - 1

    const mine = shots.filter((shot) => shot.card.box === box)
    const newest = mine[mine.length - 1]

    /* THE SERVER WINS WHERE IT IS AHEAD, AND WHERE IT IS AHEAD THE STACK COLLAPSES TO ONE.
     * This session's shots carry a rendered label and a thumbnail and `/status` carries
     * neither, so a shot is the better thing to show — but only while the two still agree
     * about which card is newest.
     *
     * They stop agreeing in exactly two ways, and both are ordinary. A capture that
     * committed and lost its response (spec 5.5) is a card the server has and this list does
     * not; so is a capture the other device made into the same box, which D13 permits by
     * design. In both cases the shot names a position that is no longer the newest, and the
     * route refuses anything but the newest — so nothing is destroyed, but the control has
     * shown the operator the wrong card and the press buys a refusal. Spec 5.4 wants an undo
     * you can aim, and aiming at a stale local guess is the thing it is arguing against.
     *
     * ONE ROW RATHER THAN A DEEP STACK IS THE SAFE ANSWER HERE, and it is the reason this
     * case is worth a paragraph rather than a line. The cards between the newest shot and
     * the server's high-water mark are cards this session never took: it has no label, no
     * photograph and no count for them. Offering to undo "back to" a shot underneath them
     * would be offering to delete somebody else's captures, sight unseen, from a list that
     * cannot draw them. So the depth is exactly one until the two agree again, which one
     * ordinary undo restores.
     */
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

  /* UNDO, `depth` CARDS OF IT, NEWEST FIRST. `depth` is 1 for `U` and for the button on the
   * top row; it is N for the Nth row of the stack, which means "this card and everything
   * captured after it".
   *
   * SEQUENTIAL, NEVER PARALLEL, and the store is what makes that non-negotiable: the route
   * deletes the newest card in a box and refuses anything else, so card N-1 is not undoable
   * until card N is gone. Firing them together would send N requests of which one could
   * succeed.
   *
   * IT HOLDS `busy` FOR THE WHOLE WALK, which is the one place this differs from the note
   * editor's rule about not blocking the shutter. A capture landing between two deletes
   * would become the newest card in the box — so the next delete in the plan is no longer
   * the newest, the server refuses it, and the walk stops halfway with a card the operator
   * meant to keep already gone. The shutter is held for a few hundred milliseconds instead.
   *
   * THE PLAN IS READ ONCE, up front. `undoStack` is derived from state this function is
   * about to change, so the value that named what would be deleted is the only value
   * entitled to say what was.
   */
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

  /* A DIVIDER, IN FRONT OF THE NEXT CARD. The owner's `S`, 2026-08-29.
   *
   * SENDS NO INDEX. `server.ts:openSection` has the argument at length: the store reads
   * `next_index` inside its own lock, so the divider lands in front of the card the next
   * capture will actually take, and there is no number here to be stale about. What this
   * function does with the answer is read back the section the SERVER rendered —
   * `sections_detail`'s last entry — rather than counting the layout array itself. Section
   * arithmetic in TypeScript is the second renderer D10 and `BoxOps.tsx` both refuse.
   *
   * THE FRESH RECORD GOES BACK INTO `boxRecords`, which is not housekeeping: that list is
   * read on mount and when the Box field opens, so without this the box the operator is
   * shooting would carry the layout it had at the top of the run for the rest of it.
   *
   * A refusal is information beside the control and never a halt — `doUndo`'s rule, and the
   * same reasoning: a refused divider changed nothing, and spec 5.5 stops the run for a card
   * that may have gone past unrecorded. Nothing here can lose a card. */
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
  const captureTrigger = triggerMode === 'motion' ? machineTrigger : keyTrigger
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
                <span className="capture-inline-label">
                  <PositionLabel label={last.card.label} flow="run" />
                </span>.
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
              <span className="capture-inline-count">{swallowed.halted}</span>{' '}
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
        {/* THE CONTROL SIDEBAR — pass D's CADENCE SPLIT, re-ordered top to bottom by the
            owner on 2026-08-24: SESSION, then the CLAIMS, then the shutter at the foot.
            The split itself is untouched — Game, Camera, Rotation and Trigger are still
            the quiet 24px group set once when the rig is set up, and Box, Set hint, Rarity
            and Finish are still the per-stack claims at 32px — what moved is which end of
            the column each one sits at.

            What the old order bet, and what this one bets instead. Pass D put the claims at
            the top and the session group under the shutter, on the reading that the rows an
            operator's eyes cross per stack should all be claims. The owner's order reads the
            column as a run instead: set the rig up at the top, claim the stack in the middle,
            and press the shutter at the bottom — so the column is walked once downward at the
            start of a run and then only its middle is touched. The shutter gains from the
            move rather than losing: it is the last thing in the panel now, so nothing that is
            added to the claims list above can ever push it further from the bottom edge.

            The mockup's own `Capture` brand head is NOT reproduced — the app nav sits 46px
            above this column already saying which screen this is, and a duplicate title is
            36px of the exact "oversized boxes" complaint this pass exists to answer. */}
        <aside className="capture-side">
          {/* THE SESSION GROUP, at the top of the column and quieter — 24px rows to the
              claims' 32, smaller type, one group caption. These four are set once when the
              rig is set up and then read, not touched: which game the stacks are, which lens
              the photos come through, which way the sensor is mounted, what fires the
              shutter. It is FIRST rather than last as of 2026-08-24 (owner), which is the
              order a run is actually set up in: rig, then stack, then shutter.

              Quiet is doing the work the position used to do. The reason this group sat
              under the shutter was to keep the rows beside a running feeder all claims, and
              the group's whole visual grammar — one size down on every face, 24px rows, a
              caption over the top — is what keeps it from competing with the claims now that
              it is above them. It reads as the header of the column rather than as four more
              things to set per stack. */}
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
                      k={OPTION_KEYS[position]}
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

            {/* C10's PRODUCT CLAIM, and it is drawn ONLY for the game that claims one.
                Which game that is comes from `registry.product_game` — the server's own
                answer — rather than from a game key written on this side, which is the
                registry mirror this file refuses everywhere else and is no more acceptable
                for one string than for a whole vocabulary.

                WHY THE CLAIM EXISTS AT ALL: code cards arrive in sealed-product batches, so
                the operator can see the box the stack came out of while the camera cannot.
                That is what retires C2's OCR half — a fiducial crop, an OCR engine, a
                character whitelist and a hand-built SKU table replaced by one picker that is
                right more often. `docs/specs/code-cards.md` §4 carries the argument.

                THE PREMIUM MARK IS THE WHOLE POINT OF THE FIELD. A Pokemon Center ETB code
                lists at roughly 46x a booster code, and the one mistake that costs real
                money on this track is a premium code leaving in a bulk lot. */}
            {registry !== null && game === registry.product_game ? (
              openField === 'product' ? (
                <OpenField
                  k="P"
                  label="Product"
                  meta={
                    product === null ? (
                      <span className="capture-val is-default">{NO_CLAIM_LABEL}</span>
                    ) : null
                  }
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
                        trail={entry.premium ? 'premium' : undefined}
                      />
                    ))}
                  </div>
                  <p className="capture-quiet">
                    Which sealed product this stack came out of. Leave it unclaimed if you do
                    not know — an unclaimed code is counted on the Codes screen and refused by
                    both channel lanes, which is louder than a wrong guess.
                  </p>
                </OpenField>
              ) : (
                <Row
                  k="P"
                  label="Product"
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
                          k={OPTION_KEYS[position]}
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

          <div className="capture-side-fields">
            {/* BOX FIRST among the claims — it is the one with a physical drawer under it.
                The game is not here at all: it lives in the session group above, because it
                decides what the other pickers may offer but is decided once per session, and
                the fields it governs simply do not render until the registry lands. */}
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
                {/* ONE ENTRY, NEVER A LIST: thirty boxes cost what three cost, because
                    nothing ever draws more than nine rows and one keystroke re-narrows.
                    Substring on the number AND the name, so `9` keeps 19 and 95 as well as
                    9, and `com` keeps "common box 3" — a box is remembered by its digits or
                    by what is written on it, not by either one's prefix.

                    THIS WAS TWO CONTROLS AND IS ONE. A filter that could only select, and an
                    `N` field that could only create, both taking digits, separated by nothing
                    but which held focus. */}
                <div className="capture-entry">
                  <span />
                  <div className="capture-entrybox">
                    <input
                      ref={boxEntryRef}
                      className="capture-filter"
                      type="text"
                      aria-label="Find a box by number or name, or type a new one"
                      placeholder="number or name, then Enter"
                      value={boxEntry}
                      disabled={boxBusy}
                      onChange={(event) => {
                        // NOT stripped to digits, which is the half that makes a box
                        // findable by what it is called. The entry is free text; what
                        // decides whether it is a number is `BOX_DIGITS`, at the one place
                        // that has to decide — the creation offer.
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
                      {/* WHAT ENTER IS ABOUT TO DO, before it is pressed. Spec 5.2 asks for
                          exactly this and calls it what it is: showing "this is a new box"
                          as information is not a confirmation step and costs nothing. Until
                          now the earliest that fact appeared was the `empty` sub AFTER the
                          switch, and the `N` field said nothing at all. */}
                      {boxBusy
                        ? 'adding…'
                        : boxTop !== undefined
                          ? boxTop.sealed
                            ? 'sealed'
                            : `next ${boxTop.next ?? '?'}`
                          : boxOffer !== null
                            ? 'new box'
                            : `${boxes.length} in use`}
                    </span>
                  </div>
                </div>
                <div className="capture-opts">
                  {boxRows.map((option) => (
                    <Opt
                      key={option.box}
                      /* NO KEY CHIP, and its absence is the merge's own consequence rather
                         than a truncation. Every keystroke in this field is typing — box
                         names are digits and letters both — so a chip here would advertise
                         a key that does nothing. It always did: the entry holds focus from
                         the moment the field opens, and the window handler bails on
                         `isEditableTarget`, so the chips these rows used to draw were
                         unreachable by keyboard for as long as they existed. */
                      on={option.box === box}
                      name={`Box ${option.box}`}
                      sfx={option.name === null ? null : ` ${option.name}`}
                      /* The store's own high-water mark, verbatim. NOT a card count — the
                         two disagree the moment a record is removed. A shut box says so
                         instead: D20 refuses a capture into one before it computes an
                         index, so the lid is the only fact about it this screen needs. */
                      trail={option.sealed ? 'sealed' : `next ${option.next ?? '?'}`}
                      onPick={() => {
                        if (option.sealed) {
                          setBoxNote(
                            `Box ${option.box} is sealed and takes no more cards. Open it ` +
                              `on the Inventory screen, or pick another.`,
                          )
                          return
                        }
                        chooseBox(option.box)
                      }}
                    />
                  ))}
                  {/* THE CREATION ROW, AND IT IS LAST. Last is what keeps "Enter takes the
                      top row" safe: it becomes the top row only when nothing matched, which
                      is exactly when creating is what was meant. Typing `com` against an
                      existing "common box 3" selects that box rather than making a junk one.

                      Its name is what will exist. Digits create that NUMBER unnamed — the
                      old `N` field's whole behaviour, kept — and anything else creates a box
                      CALLED that, with the lowest free number attached by the server. */}
                  {boxOffer === null ? null : (
                    <Opt
                      on={false}
                      name={boxOffer.box === null ? boxOffer.name ?? '' : `Box ${boxOffer.box}`}
                      trail="new"
                      /* CREATES, and never takes the top match — see `createOfferedBox`. */
                      onPick={() => void createOfferedBox()}
                    />
                  )}
                </div>
                <p className="capture-opennote">
                  {boxMatchTotal > boxRows.length
                    ? `${boxMatchTotal} boxes match; ${boxRows.length} shown. Narrow it, or press Enter to take the top row.`
                    : 'Type a number or a name, then Enter. Enter takes the top row.'}
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

            {/* Free text over a real vocabulary (D65): TCGplayer publishes the set names
                and the operator types shorthand, so the field suggests without constraining
                and JUDGES WITHOUT REFUSING. Optional, and worth the field — without it a
                collector number that matches rows in two sets reviews as `set_ambiguous`. */}
            {openField === 'set' ? (
              <OpenField
                k="H"
                label="Set hint"
                /* THE RULE, WHERE THE WORD `optional` STOOD ALONE. Optional it remains; what
                   the meta never said is that the field has a vocabulary at all, which is
                   the fact an operator needs BEFORE they type rather than after. */
                meta="optional · a real set name"
                onClose={closeField}
              >
                <form
                  className="capture-entry"
                  onSubmit={(event) => {
                    event.preventDefault()
                    /* ENTER COMPLETES BEFORE IT CLOSES. A hint that resolved through an
                       alias, a prefix or a colon-code scopes the export correctly and is
                       still not the set's NAME — which is the form `pipeline/join.py:
                       set_matches` needs at join time, one fold and no shape rules. So the
                       keystroke that leaves the field also makes the stored string exact.
                       It never invents one: nothing resolved, nothing rewritten. */
                    if (hintVerdict.state === 'matched' && !hintVerdict.exact) {
                      setSetHint(hintVerdict.set)
                    }
                    closeField()
                    blurActive()
                  }}
                >
                  <span />
                  {/* THE BOX FIELD'S OWN SHAPE, and deliberately the same one: an entry with
                      its live state pinned to the right end, reading as one control. That
                      field says `next 60` / `new box`; this one says whether what is typed
                      names a set. Two free-text fields, one grammar. */}
                  <div className="capture-entrybox">
                    <input
                      ref={hintRef}
                      className="capture-filter"
                      type="text"
                      placeholder="sv09"
                      aria-label="Set hint"
                      list="capture-set-names"
                      value={setHint}
                      onChange={(event) => setSetHint(event.target.value)}
                    />
                    {/* A DATALIST AND NOT A SELECT, which is the whole reason this is safe to
                        add to the rig's own screen. It suggests without constraining: free
                        text still works, an empty list is indistinguishable from the control
                        before D65, and nothing here can refuse a capture. */}
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
                {/* WHY THERE ARE NO SUGGESTIONS, WHICH SILENCE DOES NOT SAY. The list
                    degrading to empty is the correct behaviour — the rig never stops for an
                    autocomplete — but degrading INVISIBLY is a different thing, and an
                    expired session looks exactly like a game that has no sets. The reason
                    already rides on the response and was being thrown away.

                    IT TAKES PRECEDENCE OVER THE VERDICT, because there is no verdict: with
                    no vocabulary every hint is `unchecked`, and a sentence about what the
                    typing means would be a second sentence saying less than this one. */}
                {hintVocabulary === undefined ? null : hintVocabulary.reason ? (
                  <p className="capture-opennote">
                    {hintReason(hintVocabulary.reason)}. The hint is stored exactly as typed.
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
                right={
                  setHint.trim() === '' ? (
                    <span className="capture-val is-default">none</span>
                  ) : (
                    /* AT REST THE VERDICT IS ONE WORD OR NOTHING. A hint that names a set is
                       the ordinary case and says nothing extra; one that names none carries
                       the sub and the accent, so a stack captured against a typo is visible
                       from the row rather than only from inside the field. Silent while the
                       vocabulary has never been fetched — this screen does not accuse a
                       string it has not checked. */
                    <span className={hintAlert ? 'capture-val capture-val-alert' : 'capture-val'}>
                      {setHint.trim()}
                      {hintAlert ? <em className="capture-sub">names no set</em> : null}
                    </span>
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
                      game authors is Pokemon's thirteen, and since 2026-08-24 ALL thirteen
                      ride a key (`OPTION_KEYS`) rather than the first nine — so the box the
                      filter saved was never more than a few taps, while it cost a focused
                      input on every open of this field and a re-indexing rule the operator
                      had to hold in their head to read the chips. The alphabet strengthens
                      that ruling rather than reopening it: what a filter was for here was
                      dragging row ten into keyboard reach, and row ten has its own key now.

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

          {/* THE FOOT: the two controls that must never scroll out of reach, and as of
              2026-08-24 they are literally the foot of the panel — the owner moved the
              shutter to the bottom of the sidebar and the session group to the top.
              Everything above is a setting, chosen at the top of a run and then left alone,
              so it is what gives up room on a short window. These two are the run itself —
              the shutter, and the one control in the app that hard-deletes. A capture button
              you have to scroll a column to find is a card photographed late or not at all,
              and an undo you have to go looking for is reached for after the next card has
              already gone past.

              Being last is what makes that promise cheap to keep. Under the old order the
              session group sat below these two, so every row added to it pushed the shutter
              up away from the edge the eye returns to; nothing is below them now, and a new
              field anywhere in the column leaves the shutter exactly where it was relative to
              the bottom of the panel. */}
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

              {/* The machine's own vitals, only while it is the armed trigger, and every
                  number on this row is now one the machine actually decides on — D81's
                  rule, learned the hard way: the row carried `luma` for two rig sessions
                  while the gate read a different statistic, and a HUD showing a number
                  nothing branches on is how a rig gets debugged against the wrong one.

                  `d` is the live frame-difference and `t` is the pair of thresholds it is
                  judged against, which MOVE now — they are multiples of `typ`, this
                  session's own measured typical difference, so the operator can see the
                  machine adapt instead of taking it on faith. `Δbase` is how far the scene
                  is from the baseline and `≥` is what it must beat to count as a card.
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
                  {/* The stillness band and the measurement it is a multiple of. Every one
                      of these is `name value` with a single space, which is the shape
                      motion-live.spec.ts parses the row by — a HUD that grows a slash or a
                      unit stops being readable by the test that pins it. */}
                  <span>tlo {motionDiag.tLo.toFixed(2)}</span>
                  <span>thi {motionDiag.tHi.toFixed(2)}</span>
                  <span>typ {motionDiag.dTypical.toFixed(2)}</span>
                  {/* The presence decision, both halves: how far the scene is from the
                      session's baseline, and what it has to beat to count as a card. */}
                  <span>dbase {motionDiag.dBase.toFixed(2)}</span>
                  <span>floor {motionDiag.presenceFloor.toFixed(2)}</span>
                  {motionDiag.hasBaseline ? null : (
                    <span className="capture-refused">baseline pending</span>
                  )}
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

              {/* THE SENTENCE THE OLD MACHINE OWED AND NEVER SAID. On 2026-08-29 twenty
                  settles in a row were refused as an empty stand while a box was fed
                  through the lens, and the only trace of it on screen was a counter going
                  up beside six other counters. A RUN of refusals has exactly one likely
                  cause — the baseline was taken with something on the stand — and it has
                  exactly one remedy, which is the button under it. Three in a row rather
                  than one, because one refusal is the arm-time scene reporting itself and
                  is correct. */}
              {triggerMode === 'motion' && (motionDiag?.noCardRun ?? 0) >= 3 ? (
                <p className="capture-refused">
                  {motionDiag?.noCardRun} settles in a row read as an empty stand. If cards are
                  going past the lens, the baseline was taken with something on the stand —
                  clear it and re-baseline. Those cards were not photographed.
                </p>
              ) : null}

              {/* A CONTROL, NOT A LETTER. Every act on this screen that costs a key press —
                  the shutter, the undo, the divider — happens at feeder pace with both hands
                  on cards. Re-baselining does not: it is performed after clearing the stand,
                  with a hand already off the keyboard, and the letter it would want (`b`) is
                  the box field's. Rendered only while a machine is armed to receive it. */}
              {triggerMode === 'motion' && motionDiag !== null ? (
                <button
                  type="button"
                  className="capture-go"
                  onClick={() => motionControls.current?.rebaseline()}
                >
                  Re-baseline · stand must be empty
                </button>
              ) : null}
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
                  <span className="capture-inline-label">
                  <PositionLabel label={replayed} flow="run" />
                </span>. The paused capture
                  did reach the server, so nothing new was recorded and no position was used.
                  Move on to the next card.
                </p>
              )}
            </div>

            {/* THE THIRD ACT, BETWEEN THE TWO THAT WERE ALREADY HERE, and the order is the
                order they are performed in: shoot the stack, drop a divider in when you
                reach one, undo the card you just took. It is in the foot rather than up
                among the fields because it is not a claim — nothing about it changes what
                the next photograph will say about itself — and because it is pressed at the
                box, which is the argument the foot's own comment makes for the other two.

                DISABLED WITHOUT A BOX, WHICH IS THE ONE STATE IT HAS. docs/DESIGN.md's
                absent-not-disabled rule is about the control that COMMITS to something
                irreversible — the run panel's spend button, the listing release on the box
                header — and this is neither: it is free, it is reversible in the dividers
                editor, and it is the next thing to press. A control that vanished until a box was picked would
                read as a screen with a missing feature on the one screen the owner cannot
                afford to look for things on. */}
            <div className="capture-section">
              <button
                type="button"
                className="capture-go"
                onClick={() => void doSection()}
                disabled={box === null || sectionBusy}
              >
                New section <kbd className="capture-key">{SECTION_KEY_LABEL}</kbd>
              </button>
              {sectionNote === null ? null : (
                <p className={sectionNote.done ? 'capture-quiet' : 'capture-refused'}>
                  {sectionNote.text}
                  {/* The section and its first card in the utility face, inline in a body
                      sentence — the same treatment the undo receipt gives the position it
                      deleted, and the same reason: this is metadata, and mixing it into the
                      body face would make a number read as a word. */}
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

            {/* Always visible, never appearing after a capture: a control that appears and
                disappears is one you have to look for at the moment you are least inclined
                to. It was a full-width strip under the frames until the owner said it "can
                clearly be on the side too", and that strip was ~90px of the height this
                layout needed back. */}
            {/* THE UNDO STACK — the owner's ask of 2026-08-29: "a list of 10 rather than the
                one I can see right now". It was one card with one button; it is every
                capture this session made into this box, newest first, each row its own
                control.

                EVERY ROW IS A BUTTON AND A ROW IS NOT A DELETE. Pressing row N undoes N
                cards — that row and everything captured after it — because D10 lets undo
                reach the newest capture in a box and nothing else, and walking is how it
                reaches further. The count is drawn on the row so the press cannot be made
                without seeing it: the number IS how many cards go, and it is the row's
                ordinal, which are the same number by construction.

                Still no dialog, still one tap (spec 5.4). The deleted photo is of a card
                still within reach of the hand that fed it, so the remedy for a wrong undo is
                to photograph it again — which is why this is the stated exception to the
                no-confirm rule rather than a violation of it. Allowed while the run is
                halted: the halt is about capturing, and correcting the last good card is
                exactly what a stopped run is for. */}
            <footer className="capture-undo">
              <p className="capture-field-name">
                Undo
                {undoStack.length > 1 ? (
                  /* WHAT THE LIST HOLDS, beside its name, because the list is capped and
                     scrolls — a capped list that does not say so reads as a short one, which
                     is `BoxOps`' section list making the same mistake one screen over. */
                  <span className="capture-undo-depth">{undoStack.length} recent</span>
                ) : null}
              </p>

              {undoStack.length === 0 ? (
                <p className="capture-quiet">Nothing in this box to undo.</p>
              ) : (
                <>
                  <ul className="capture-undo-list">
                    {undoStack.map((target, at) => (
                      <li key={`${target.box}/${target.index}`}>
                        <button
                          type="button"
                          className="capture-undo-row"
                          onClick={() => void undoBack(at + 1)}
                          disabled={busy}
                          /* The visible row is a thumbnail, a position and a number, and the
                             number means something a screen reader cannot infer from it. So
                             the accessible name says the act in full — and says it
                             differently for the top row, which is the one `U` fires. */
                          aria-label={
                            at === 0
                              ? `Undo the newest capture, ${positionText(target)}`
                              : `Undo ${at + 1} captures, back to ${positionText(target)}`
                          }
                        >
                          {/* Empty alt on purpose, not by omission: the position beside it is
                              the same fact in words, and what the thumbnail adds — whether
                              this is the card you meant — is not a thing alt text can
                              carry. */}
                          <img
                            className="capture-undo-thumb capture-undo-thumb-portrait"
                            src={photoSrc(target.box, target.index, revision)}
                            alt=""
                          />
                          <span className="capture-undo-pos">
                            {/* THROUGH THE SHARED COMPONENT, because D41 lists this
                                sidebar as one of the six owner sites that draw an
                                address as a rank rather than a dotted list. This branch
                                predates that entry by 32 commits and drew a bare string;
                                the stack is the feature and the treatment is a rule about
                                how any address is drawn, so the row keeps one and gains
                                the other. The 20px figure is set in the stylesheet, once,
                                where the site's register belongs. */}
                            <PositionLabel label={positionText(target)} />
                          </span>
                          {/* The top row carries its KEY and every other row carries its
                              DEPTH. They are different kinds of fact in the same slot, which
                              is legible only because the top row's is the one letter this
                              screen has always drawn there and the rest are plain counts. */}
                          <span className="capture-key">
                            {at === 0 ? UNDO_KEY_LABEL : at + 1}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                  {undoStack.length > 1 ? (
                    <p className="capture-quiet">
                      A row undoes that card and everything captured after it.
                    </p>
                  ) : null}
                </>
              )}

              {undoNote === null ? null : (
                <p className={undoNote.done ? 'capture-quiet' : 'capture-refused'}>
                  {/* A WALK THAT STOPPED EARLY SAYS SO FIRST, before the server's own
                      sentence, because it is the half the operator cannot see: the cards
                      that went and the cards that did not have both left the list. Our
                      sentence is added to the server's, never folded into it — the copy rule
                      shows the server's message verbatim. */}
                  {undoNote.did !== undoNote.want ? (
                    <span className="capture-undo-partial">
                      Undid {undoNote.did} of {undoNote.want}.{' '}
                    </span>
                  ) : null}
                  {undoNote.text}
                  {undoNote.done && undoNote.did > 1 ? ` ${undoNote.did} captures, back to` : null}
                  {/* The position in the utility face, inline in a body sentence — the same
                      string the server rendered when the card was captured. This used to say
                      "Undone 3/7": the store's own key, in the body face, naming a thing the
                      operator has never seen on any screen. */}
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
                  <p className="capture-label">
                    <PositionLabel label={last.card.label} />
                  </p>
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
