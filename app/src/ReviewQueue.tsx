import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { PositionLabel } from './PositionLabel'
import { isEditableTarget } from './keys'
import type {
  AnswerResult,
  CandidateRow,
  CatalogLookup,
  Place,
  QueueEntryWire,
  QueueName,
  QueueRead,
  QueueSnapshot,
  RetireReason,
  ServerStatus,
  StandDownReason,
} from './types'
import type { Failure } from './server'
import {
  ServerError,
  answerReview,
  answerReviewGroup,
  describeFailure,
  getQueues,
  getRuns,
  getStatus,
  isDeparted,
  neighborWords,
  placeParts,
  photoUrl,
  refreshQueues,
  retireCard,
  reviewCatalog,
  standDown,
  undoAnswer,
  undoRetire,
  undoStandDown,
} from './server'
import { Button, EmptyState, Icon, IconButton, Kbd, Money, Notice, Page, Pill, ReloadButton, Sheet } from './kit'
import { toast } from './kit/toast'
import { LogWell } from './RunsLog'
import { useOverlayFocus } from './runsOverlay'
import { RunsContent, boxInHash, perCardRate, runInHash, stateInHash } from './Runs'
import { roundsToNothing } from './money'
import './ReviewQueue.css'
import { isRetiredReason, reasonLabel } from './reasons'
import { collectorNumber as sharedCollectorNumber } from './cardNumber'

/* THE REVIEW QUEUE — the judgement screen. One card at a time: the photograph on a dark
 * stage, the question it poses, the evidence, and one row per answer with a keycap on it.
 * Answering writes and advances; a receipt with an undo stands beside the rows for twenty
 * seconds and then in the session list. The worked order, the keyboard model, the optimistic
 * advance, the stale-refusal set and the group write are unchanged from the screen this
 * replaces — what changed is what is drawn where.
 *
 *   GET  /queues                      both standing queues, in worked order
 *   POST /review/<box>/<index>/answer one candidate row, or {"undo": true} (D28)
 *   POST /review/group-answer         a homogeneous group answered in one write
 */

// ------------------------------------------------------------------------- the sentence

type Segment =
  | { kind: 'text'; text: string }
  /** A machine string: a collector number or a set hint. Mono (CLAUDE.md's three type
   *  roles). */
  | { kind: 'value'; text: string }
  /** A card's own name. Never mono (UX-270): a name is prose, not a machine string, and the
   *  three type roles reserve the mono face for SKUs, run names, reason codes, key caps and
   *  card numbers alone. */
  | { kind: 'name'; text: string }
  /** A claim is drawn as a word; the pipeline's own spelling rides in `raw` for the title. */
  | { kind: 'claim'; text: string; raw: string }

const say = (text: string): Segment => ({ kind: 'text', text })
const value = (text: string): Segment => ({ kind: 'value', text })
const cardName = (text: string): Segment => ({ kind: 'name', text })
const claim = (raw: string, word: string = humanize(raw)): Segment => ({ kind: 'claim', text: word, raw })

/** A trimmed field, or null. Every field of `read` is treated as absent-or-blank. */
function text(field: string | null | undefined): string | null {
  if (typeof field !== 'string') return null
  const trimmed = field.trim()
  return trimmed === '' ? null : trimmed
}

/** D3 rung 1's finish claim as its members, or null. A bare string reads as one member: a
 *  `review.json` written before the claim became a set is still a file this screen opens. */
function claimMembers(field: string | string[] | null | undefined): string[] | null {
  const members = (typeof field === 'string' ? [field] : Array.isArray(field) ? field : [])
    .filter((member): member is string => typeof member === 'string')
    .map((member) => member.trim())
    .filter((member) => member !== '')
  return members.length === 0 ? null : members
}

/* The raw pair, on purpose (D67): this screen judges the read that put the card in its box,
 * so it shows exactly what the model returned, set code and all. */
function collectorNumber(read: QueueRead): string | null {
  return sharedCollectorNumber({ number: read.number, printed_total: read.printed_total })
}

/* The rarities the CANDIDATE ROWS carry, deduplicated in the order they are drawn. Half of
 * what `rarity_claim_mismatch` means, and absent on every entry queued before 2026-09-11 —
 * which is an ordinary case, not a migration: a queue file outlives the run that wrote it,
 * and the sentence falls back to the wording it had. */
function candidateRarities(candidates: CandidateRow[]): string[] | null {
  const seen: string[] = []
  for (const row of candidates) {
    const rarity = text(row.rarity)
    if (rarity !== null && !seen.includes(rarity)) seen.push(rarity)
  }
  return seen.length === 0 ? null : seen
}

/* English for a short list, so a sentence can say "Rare or Epic" rather than printing an
 * array. Two is the common case and three is the ceiling this has ever drawn. */
function orList(words: string[]): string {
  if (words.length <= 1) return words[0] ?? ''
  return `${words.slice(0, -1).join(', ')} or ${words[words.length - 1]}`
}

function soleCondition(candidates: CandidateRow[]): string | null {
  const conditions = new Set(candidates.map((row) => row.condition))
  if (conditions.size !== 1) return null
  const [only] = [...conditions]
  return text(only)
}

function duplicatedCondition(candidates: CandidateRow[]): string | null {
  const seen = new Set<string>()
  for (const row of candidates) {
    if (seen.has(row.condition)) return text(row.condition)
    seen.add(row.condition)
  }
  return null
}

/* One sentence per reason. A claim is drawn as a word; its pipeline spelling is kept on the
 * segment so the title still greps against the run report. */
function sentence(entry: QueueEntryWire): Segment[] {
  /* A code the product has stopped asking about, on a card queued before it stopped. Said
   * here rather than left to fall through to the default, which blames the pipeline for a
   * sentence this screen deleted on purpose. */
  if (isRetiredReason(entry.reason)) {
    return [
      say('This screen no longer asks this question — the answer was the same listing either way. The card was queued before it was dropped: the listings below are the ones that matched, and answering one lists it.'),
    ]
  }

  const number = collectorNumber(entry.read)
  const sortedMembers = claimMembers(entry.read.metadata_finish)
  const toggle = sortedMembers?.join(' or ') ?? null
  const toggleWord = sortedMembers?.map(humanize).join(' or ') ?? null
  const detected = text(entry.read.detected_finish)
  const hint = text(entry.read.set_hint)
  const name = text(entry.read.name)
  const claimed = claimMembers(entry.read.rarity_claim)
  const only = soleCondition(entry.candidates)

  switch (entry.reason) {
    case 'no_catalog_row':
      return number === null
        ? [say('TCGplayer has no listing for this card.')]
        : [say('TCGplayer has no listing for '), value(number), say('.')]

    case 'number_unread_name_matched': {
      const head: Segment[] =
        number === null
          ? [say('No collector number could be read from this photograph. ')]
          : [say('The number read as '), value(number), say(', which is in no listing. ')]
      const matched: Segment[] =
        only === null
          ? [say(' matched one listing in this set by name.')]
          : [say(' matched one '), claim(only), say(' listing in this set by name.')]
      return name === null
        ? [...head, say('The name matched one listing in this set.')]
        : [...head, cardName(name), ...matched]
    }

    case 'metadata_not_stocked': {
      if (toggle === null || toggleWord === null) return [say('TCGplayer has no listing for the finish recorded on this stack.')]
      const head = [say('You sorted this stack as '), claim(toggle, toggleWord)]
      return only === null
        ? [...head, say(', and TCGplayer has no such listing for this number.')]
        : [...head, say(', and TCGplayer has only '), claim(only), say(' for this number.')]
    }

    case 'detected_finish_not_stocked': {
      const head = [say('The photograph reads as '), detected === null ? say('a finish this entry does not record') : claim(detected)]
      return only === null
        ? [...head, say(', and TCGplayer has no such listing for this number.')]
        : [...head, say(', and TCGplayer has only '), claim(only), say(' for this number.')]
    }

    case 'ambiguous_no_signal':
      return [say('No finish recorded, and the photograph didn\'t settle it — every listing below is possible.')]

    case 'duplicate_condition': {
      const duplicate = duplicatedCondition(entry.candidates)
      return duplicate === null
        ? [say('Two of TCGplayer\'s listings claim the same condition for this number — nothing can choose between them.')]
        : [say('Two of TCGplayer\'s listings claim '), claim(duplicate), say(' for this number — nothing can choose between them.')]
    }

    case 'low_confidence': {
      const head: Segment[] =
        name === null
          ? [say('The system read this photograph as a card it could not name')]
          : [say('The system read this photograph as '), cardName(name)]
      const middle: Segment[] = number === null ? [] : [say(' '), value(number)]
      const confidence = text(entry.confidence) ?? 'low'
      return [...head, ...middle, say(', with '), claim(confidence, confidence.replace(/[_-]+/g, ' ')), say(' confidence, which is not enough to list it on.')]
    }

    case 'no_position':
      return [say('This card has no box or index recorded — this screen can\'t say where it is.')]

    case 'identification_failed':
      return [say('Identification returned nothing at all for this photograph.')]

    case 'set_ambiguous': {
      const head: Segment[] = number === null ? [say('This collector number ')] : [value(number), say(' ')]
      const tail: Segment[] =
        hint === null
          ? [say('and no set hint was recorded to break the tie.')]
          : [say('and the set hint '), value(hint), say(' names none of them.')]
      return [...head, say('matches listings in more than one set, '), ...tail]
    }

    case 'card_not_detected':
      return [say('No card found in this photograph — no number corner to crop or read.')]

    case 'no_market_data':
      return [say('This listing carries no market price — a missing price is unknown, not low.')]

    /* D23's job (a): the only reason that can mean the rows themselves are the wrong card.
     *
     * IT NAMES BOTH WORDS SINCE 2026-09-11, AND IT NAMED NEITHER BEFORE. The one reason in
     * the vocabulary whose meaning is "A contradicts B" could not say what A or B were, so
     * 141 entries on the owner's screen said the claim matched no row and left them to work
     * out which word disagreed with which. The wire carries both now — `read.rarity_claim`
     * and each candidate's `rarity` — and when it does not, the old wording stands: an
     * entry queued before the fields existed is not an entry to guess about. */
    case 'rarity_claim_mismatch': {
      const rowWords = candidateRarities(entry.candidates)
      const head: Segment[] =
        claimed !== null && rowWords !== null
          ? [
              say('You claimed this stack holds '),
              claim(claimed.join(' or '), orList(claimed.map(humanize))),
              say(number === null ? ', and every listing below is ' : ', and every listing '),
              ...(number === null ? [] : [value(number), say(' found is ')]),
              claim(rowWords.join(' or '), orList(rowWords.map(humanize))),
              say('. '),
            ]
          : number === null
            ? [say('The rarities claimed at capture match none of the listings below. ')]
            : [say('The rarities claimed at capture match none of the listings '), value(number), say(' found. ')]
      return [
        ...head,
        say('A confident misread number can land on real listings for a different card. Check against the photograph before answering.'),
      ]
    }

    /* The same cross-check run the other way, and the reason with the strongest claim on a
     * human's attention: the number found rows and the NAME read off the same photograph
     * matches none of them. `pipeline/routing.py:NAME_DISPUTED`. */
    case 'name_disputed': {
      /* THE NUMBER'S ROW IS FOUND BY PROVENANCE, NOT BY POSITION. It was `candidates[0]`
       * until 2026-09-12, when the name's own match moved to the head of the list — reading
       * the first row now would say *"reads as Deathgrip, but 162/221 is Deathgrip"*. An
       * entry written before `found_by` existed answers null here and takes the shorter
       * wording rather than naming a row on a guess. */
      const rowName = text(numberMatch(entry.candidates)?.name ?? entry.candidates[0]?.name)
      const offersBoth = entry.candidates.some((row) => row.found_by === 'name')
      const head: Segment[] =
        name === null
          ? [say('The name on this photograph could not be checked against the listing below. ')]
          : rowName === null
            ? [say('This photograph reads as '), cardName(name), say(', which is not what the listing below is called. ')]
            : [
                say('This photograph reads as '),
                cardName(name),
                say(number === null ? ', but the listing it matched is ' : ', but '),
                ...(number === null ? [] : [value(number), say(' is ')]),
                value(rowName),
                say('. '),
              ]
      return [
        ...head,
        say('The number and the name came off the same card and they disagree — one was misread. Check against the photograph before answering.'),
        /* BOTH READINGS ARE ON THE LIST SINCE 2026-09-12, so the sentence says which is
         * which. Only where the name actually found something: a card whose name matched no
         * row still offers the number's row alone, and promising a second reading that is
         * not there would be worse than the silence it replaced. */
        ...(offersBoth
          ? [
              say(' Both readings are below — what the name found first, then what the number found. Neither is assumed right: the photograph settles it.'),
            ]
          : []),
      ]
    }

    default:
      return [say('No sentence written for this reason. The code below is what it said.')]
  }
}

/* The question each reason poses, as a headline. A NEW map rather than an edit to
 * `reasons.ts`: those labels are read by `#/inventory` too, and they name what happened;
 * these name what is being asked.
 *
 * A reason with no entry here is not asked about — a retired code draws the headline below
 * instead, and an unknown one draws its label. */
const QUESTIONS: Readonly<Record<string, string>> = {
  no_catalog_row: 'Which listing is this card?',
  metadata_not_stocked: 'Which finish is stocked?',
  rarity_claim_mismatch: 'Is this the right card at all?',
  detected_finish_not_stocked: 'Which finish is this?',
  ambiguous_no_signal: 'Which finish is this?',
  duplicate_condition: 'Which of the two listings?',
  low_confidence: 'Is this the card?',
  no_position: 'Where is this card?',
  identification_failed: 'What is this card?',
  set_ambiguous: 'Which set is it from?',
  card_not_detected: 'What is in this photograph?',
  number_unread_name_matched: 'Is this the listing it matched?',
  name_disputed: 'Is this the right card at all?',
  no_market_data: 'Is this the card?',
  /* `pipeline/routing.py:LISTING_DISPUTED` (identity-follows-sku.md §7.3, lane 2): a held
   * card from `cards identity --write` — the read disputes the SKU it is bound to, and
   * nobody has looked. `reasons.ts` carries the shorter sub-label under this headline. */
  listing_disputed: 'Is the listing the right card?',
}

const RETIRED_HEADLINE = 'This question was retired.'

function questionFor(reason: string): string {
  const asked = QUESTIONS[reason]
  if (asked !== undefined) return asked
  return isRetiredReason(reason) ? RETIRED_HEADLINE : reasonLabel(reason)
}

// ------------------------------------------------------------------------- the evidence

/* A pipeline enum as a word. The sentence, the chips and the facts draw the word and carry
 * the raw spelling in their title, so the run report is still one hover away. */
const FINISH_WORDS: Readonly<Record<string, string>> = {
  reverse_holo: 'Reverse holo',
  reverse_holofoil: 'Reverse holo',
  holo: 'Holo',
  holofoil: 'Holo',
  foil: 'Foil',
  normal: 'Normal',
  non_holo: 'Normal',
}

function humanize(raw: string): string {
  const known = FINISH_WORDS[raw.toLowerCase()]
  if (known !== undefined) return known
  const spaced = raw.replace(/[_-]+/g, ' ').trim()
  return spaced === '' ? raw : spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

/** The claims in play for a card: what the stack was sorted as (Capture's Finish field),
 *  and what the photograph read. */
type Claims = { sorted: string[] | null; photo: string | null; hint: string | null }

function claimsOf(entry: QueueEntryWire): Claims {
  return {
    sorted: claimMembers(entry.read.metadata_finish),
    photo: text(entry.read.detected_finish),
    hint: text(entry.read.set_hint),
  }
}

/* The reasons whose claims are about the FINISH, and so can be placed on the rows. All
 * three are LIVE questions; a retired code is deliberately not among them, so the chips and
 * the row tags that were the apparatus of its question come down with it. What the stack was
 * sorted as and what the photograph read stay on the record either way — `Facts` draws both
 * for every card. */
const FINISH_REASONS: ReadonlySet<string> = new Set(['metadata_not_stocked', 'detected_finish_not_stocked', 'ambiguous_no_signal'])

/** Whether a pipeline finish spelling names an export condition string. FAILS CLOSED: an
 *  unrecognised spelling on either side tags nothing rather than mis-tagging. */
function finishMatches(finish: string, condition: string): boolean {
  const f = finish.toLowerCase().replace(/[_-]+/g, ' ').trim()
  const c = condition.toLowerCase()
  const reverse = c.includes('reverse')
  const holo = c.includes('holo')
  const foil = c.includes('foil')
  if (f === 'reverse holo' || f === 'reverse' || f === 'reverse holofoil' || f === 'reverse foil') return reverse
  if (f === 'holo' || f === 'holofoil') return holo && !reverse
  if (f === 'foil') return foil && !holo && !reverse
  if (f === 'normal' || f === 'non holo' || f === 'nonholo' || f === 'regular' || f === 'none') return !reverse && !holo && !foil
  return false
}

type Evidence = 'sorted' | 'photo' | 'name' | 'number'

const TAG_WORDS: Readonly<Record<Evidence, string>> = {
  sorted: 'sorted as',
  photo: 'photo',
  name: 'name',
  number: 'number',
}

const TAG_TITLES: Readonly<Record<Evidence, string>> = {
  sorted: 'The finish this stack was sorted as',
  photo: 'The finish the photograph read as',
  name: 'Found by the name read off this photograph',
  number: 'Found by the collector number read off this photograph',
}

/* WHICH SIGNAL ARGUED FOR THIS ROW, drawn only where the list holds more than one answer.
 *
 * `found_by` is on the wire wherever `cli/resolve.py:_candidate_rows` was handed a
 * non-empty `name_matched`, which was `name_disputed` alone until D253
 * (2026-09-23): a card already queued for a reason of its own — `ambiguous_no_signal`,
 * `rarity_claim_mismatch`, `set_ambiguous` — can now carry both readings too, under its
 * OWN reason. Reading the FIELD rather than the reason code is deliberate and is what
 * makes that extension free: the reason is the server's word for the question, and the
 * provenance is a property of the row — a later rung that offers two readings gets the
 * tags for free, and a queue entry written before the field existed draws none rather
 * than drawing a wrong one.
 *
 * THE TWO FAMILIES NEVER COLLIDE ON ONE ROW, but not because their reason codes are
 * disjoint any more — `rarity_claim_mismatch` is in `FINISH_REASONS` and can now carry
 * `found_by` too. The early return below is what keeps them apart: a row stamped
 * `found_by` never falls through to the sorted/photo finish check, whatever its entry's
 * reason is. */
function tagsFor(entry: QueueEntryWire, claims: Claims, candidate: CandidateRow): Evidence[] {
  if (candidate.found_by !== undefined) return [candidate.found_by]
  if (!FINISH_REASONS.has(entry.reason)) return []
  const tags: Evidence[] = []
  if (claims.sorted !== null && claims.sorted.some((member) => finishMatches(member, candidate.condition))) tags.push('sorted')
  if (claims.photo !== null && finishMatches(claims.photo, candidate.condition)) tags.push('photo')
  return tags
}

/** The row the NUMBER found, on an entry carrying both readings. Null when the wire does not
 *  say — an entry written before `found_by` existed, which must read as "unknown" rather than
 *  silently nominating `candidates[0]`, now that the first row is the NAME's. */
function numberMatch(candidates: CandidateRow[]): CandidateRow | null {
  return candidates.find((row) => row.found_by === 'number') ?? null
}

/** A condition's GRADE — the part of it the group offer may cluster on, with the finish
 *  folded away. `Near Mint` and `Near Mint Foil` are one grade and two finishes, and D137
 *  fixes the grade by rule, so splitting a group on the full string can only ever ask the
 *  operator to confirm the same thing twice.
 *
 *  FAILS TOWARDS NOT GROUPING, which is what makes a string test acceptable on this side.
 *  The authority is `server/capture_server.py:_condition_grade`, which reads the game's own
 *  `condition_by_finish` off the registry; the wire carries no game, so this recognises the
 *  spelling instead. A condition it does not recognise — a future game's, or `Unopened` —
 *  becomes its own grade and is grouped only with itself, so the worst this can do is offer
 *  one group fewer than the route would have accepted. It can never offer one the route
 *  refuses, which is the direction that matters. */
function gradeOf(condition: string): string {
  return /^near\s+mint\b/i.test(condition.trim()) ? 'near mint' : condition
}

/** When every candidate is one card in several finishes, the card is named once and the
 *  rows carry only what differs. Null when the rows differ in name, set or number. */
function sharedHead(candidates: CandidateRow[]): { name: string; set: string; number: string } | null {
  const first = candidates[0]
  if (first === undefined || candidates.length < 2) return null
  for (const row of candidates) {
    if (row.name !== first.name || row.set !== first.set || row.number !== first.number) return null
  }
  return { name: first.name, set: first.set, number: first.number }
}

// -------------------------------------------------------------------------------- money

/* A market price for COMPARISON ONLY. Blank and zero are unknown, never cheap (D9). */
function priceOf(market: string | null | undefined): number | null {
  if (typeof market !== 'string') return null
  const trimmed = market.trim()
  if (trimmed === '') return null
  const parsed = Number(trimmed)
  if (!Number.isFinite(parsed) || parsed <= 0) return null
  return parsed
}

function priceText(market: string | null | undefined): string {
  const parsed = priceOf(market)
  return parsed === null ? 'no market price' : `$${(market ?? '').trim()}`
}

/* D9's threshold — `pipeline/pricing.py:THRESHOLD`, and the cut between review and parked. */
const THRESHOLD = 0.4

type Band = 'top' | 'high' | 'mid' | 'low' | 'unpriced'

function bandOf(market: string | null | undefined): Band {
  const price = priceOf(market)
  if (price === null) return 'unpriced'
  if (price >= THRESHOLD * 25) return 'top'
  if (price >= THRESHOLD * 5) return 'high'
  if (price >= THRESHOLD) return 'mid'
  return 'low'
}

/** A `first_seen` as a date a person reads — `Aug 24` — and the raw string when it is not
 *  one. A date-only string is read as a local day so it does not slip back a day west of UTC. */
function sinceText(raw: string): string {
  const parsed = new Date(/^\d{4}-\d{2}-\d{2}$/.test(raw) ? `${raw}T00:00` : raw)
  if (Number.isNaN(parsed.getTime())) return raw
  return parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

/** How long this card has been waiting — the server's arithmetic, never this file's. */
function seenText(entry: QueueEntryWire): ReactNode {
  const raw = text(entry.first_seen)
  const since = raw === null ? 'not recorded' : `since ${sinceText(raw)}`
  const age = entry.age_days
  if (typeof age !== 'number') return raw === null ? since : since
  return (
    <span className="review-fact-multi">
      <span>{age}d</span>
      <span>{since}</span>
    </span>
  )
}

function ageText(entry: QueueEntryWire): string | null {
  const age = entry.age_days
  if (typeof age !== 'number' || age < 1) return null
  return `${age}d`
}

function durationText(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000))
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  if (minutes === 0) return `${seconds} s`
  return `${minutes} min ${seconds} s`
}

// -------------------------------------------------------------------------------- keys

const MAX_KEYED_CANDIDATES = 9
// HOW MANY MORE ROWS ONE "SHOW MORE" PRESS REVEALS, off rows `GET /review/<box>/<index>/
// catalog` already sent — never a second fetch. The owner's own words: "a 'show 10 more'
// etc." Rows past `MAX_KEYED_CANDIDATES` stay mouse-only either way (`CandidateButton`).
const CATALOG_REVEAL_STEP = 10
const SKIP_KEY = 's'
const SKIP_KEY_LABEL = 'S'
const CLEAR_KEY = 'c'
const CLEAR_KEY_LABEL = 'C'
const RELOAD_KEY = 'r'
const RELOAD_KEY_LABEL = 'R'
const UNDO_KEY = 'u'
const UNDO_KEY_LABEL = 'U'
const CLOSE_KEY = 'x'
const CLOSE_KEY_LABEL = 'X'
const LOOKUP_KEY = 'l'
const LOOKUP_KEY_LABEL = 'L'
const GROUP_KEY = 'g'
const GROUP_KEY_LABEL = 'G'

/* Ten answers deep and no clock on the REVERSAL (D28, rebased to a count): the last ten
 * answers stay reversible until ten more push them out. What the twenty seconds governs now
 * is only how long the newest receipt stands beside the rows before it settles into the
 * session list, where its undo is still live. */
const UNDO_DEPTH = 10
const RECEIPT_TRAY_MS = 20000

type CloseChoice =
  | { kind: 'stand_down'; reason: StandDownReason }
  | { kind: 'retire'; reason: RetireReason }

/* D37. Delete is deliberately absent: it renumbers the box and has no undo, so it stays on
 * Inventory where the box being renumbered is the thing on screen. */
const CLOSE_CHOICES: { choice: CloseChoice; label: string; machine: string; note: string }[] = [
  { choice: { kind: 'stand_down', reason: 'wasted_position' }, label: 'Wasted position', machine: 'wasted_position', note: 'A double feed, a divider, a blank — nothing worth listing.' },
  { choice: { kind: 'stand_down', reason: 'cannot_settle' }, label: 'Cannot settle it', machine: 'cannot_settle', note: 'The photograph will not decide this, and it is not worth re-shooting.' },
  { choice: { kind: 'stand_down', reason: 'not_listing' }, label: 'Not listing it', machine: 'not_listing', note: 'A real card you have decided not to list. It keeps its slot.' },
  { choice: { kind: 'retire', reason: 'pulled' }, label: 'Pulled', machine: 'pulled', note: 'Taken out of the box by hand.' },
  { choice: { kind: 'retire', reason: 'damaged' }, label: 'Damaged', machine: 'damaged', note: 'Not sellable at the condition listed.' },
  { choice: { kind: 'retire', reason: 'lost' }, label: 'Lost', machine: 'lost', note: 'Gone, and not sold.' },
  { choice: { kind: 'retire', reason: 'given_away' }, label: 'Given away', machine: 'given_away', note: 'It left without a sale.' },
]

// ------------------------------------------------------------------------------ the rows

/** One entry with the queue it came from. Prefixed key: a position can be in both files. */
type Row = {
  key: string
  queue: QueueName
  entry: QueueEntryWire
  /** The OTHER queue holding this position open, when there is one. */
  shadow?: QueueName
}

function rowsOf(snapshot: QueueSnapshot): Row[] {
  const open = (entries: QueueEntryWire[], queue: QueueName): Row[] =>
    entries.filter((entry) => !entry.cleared_by_human).map((entry) => ({ key: `${queue}:${entry.position}`, queue, entry }))
  return [...open(snapshot.review, 'review'), ...open(snapshot.parked, 'parked')]
}

/** One row per POSITION, review before parked — the row the answer route validates against. */
function oneCardPerPosition(rows: Row[]): Row[] {
  const at = new Map<string, number>()
  const merged: Row[] = []
  for (const row of rows) {
    const seen = at.get(row.entry.position)
    if (seen === undefined) {
      at.set(row.entry.position, merged.length)
      merged.push(row)
      continue
    }
    const kept = merged[seen]
    if (kept !== undefined) merged[seen] = { ...kept, shadow: row.queue }
  }
  return merged
}

/** Which queues the answer route says it cleared, or null when it did not say. */
function clearedQueues(result: unknown): ReadonlySet<QueueName> | null {
  if (typeof result !== 'object' || result === null) return null
  const body = result as { review_cleared?: unknown; parked_cleared?: unknown }
  if (typeof body.review_cleared !== 'boolean' && typeof body.parked_cleared !== 'boolean') return null
  const cleared = new Set<QueueName>()
  if (body.review_cleared === true) cleared.add('review')
  if (body.parked_cleared === true) cleared.add('parked')
  return cleared
}

/* The refusals that mean this screen is holding a queue the server has moved past. None is a
 * card to put back; every message ends by asking for a reload. */
const STALE_CODES: ReadonlySet<string> = new Set([
  'already_answered',
  'not_in_queue',
  'sku_not_a_candidate',
  'condition_mismatch',
  'group_entry_refused',
  'group_not_uniform',
])

function isStale(err: unknown): boolean {
  return err instanceof ServerError && STALE_CODES.has(err.code)
}

/** Whether the answer just written can be taken back — the OBJECT, never its members. */
function canTakeBack(result: AnswerResult): boolean {
  const origin: unknown = result.restores_to
  return typeof origin === 'object' && origin !== null
}

/* Refusals after which the undo control comes down, because pressing again answers identically. */
const FINAL_UNDO_CODES: ReadonlySet<string> = new Set(['not_answered', 'not_in_queue', 'undo_too_late', 'answer_origin_unknown'])

function isFinalRefusal(err: unknown): boolean {
  return err instanceof ServerError && FINAL_UNDO_CODES.has(err.code)
}

type UndoTarget = { box: number; index: number; position: string; label: string }

type Receipt = {
  key: string
  targets: UndoTarget[]
  label: string
  dropped: Row[]
  at: number
  said: string
  /** UX-255: the one verb for the act ("Closed") is `said`. This is the ONE place the
   *  outcome still shows — "left in place" or "retired" — as a description, never as a
   *  second verb competing with `said`. Unset for an answer's own receipt. */
  outcome?: string
  /** Which session counter this write moved, so an undo can move it back. */
  counts: 'answered' | 'closed'
  reverse: (box: number, index: number) => Promise<unknown>
  /** UX-205: every write gets a receipt. Not every write is reversible — `canTakeBack`'s
   *  `restores_to` check is real, and a card the server cannot restore keeps its receipt
   *  with the Undo control simply left off it. */
  undoable: boolean
}

type Refusal = { failure: Failure; at: string | null }

type Tally = { answered: number; closed: number; skipped: number }

/** Whether the viewport is a phone, for the one control that changes shape there. */
function usePhone(): boolean {
  const query = '(max-width: 767px)'
  const [phone, setPhone] = useState(() => (typeof window === 'undefined' ? false : window.matchMedia(query).matches))
  useEffect(() => {
    const media = window.matchMedia(query)
    const onChange = () => setPhone(media.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])
  return phone
}

export function ReviewQueue() {
  const phone = usePhone()
  const [rows, setRows] = useState<Row[] | null>(null)
  const [refusal, setRefusal] = useState<Refusal | null>(null)
  const [reloads, setReloads] = useState(0)
  const [deferred, setDeferred] = useState<readonly string[]>([])
  const [reasonFilter, setReasonFilter] = useState<string | null>(null)
  const [grouping, setGrouping] = useState(false)
  const [closing, setClosing] = useState(false)
  const [lookup, setLookup] = useState<CatalogLookup | null>(null)
  const [lookupFailed, setLookupFailed] = useState<string | null>(null)
  const [typed, setTyped] = useState('')
  const [lookingAt, setLookingAt] = useState<string | null>(null)
  const [photoAbsent, setPhotoAbsent] = useState<string | null>(null)
  const [receipts, setReceipts] = useState<readonly Receipt[]>([])
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [loading, setLoading] = useState(true)
  const loadingRef = useRef(true)

  /* This session, counted on this device: what was answered, closed and skipped since the
   * screen was opened. Client-side only — the progress bar and the reward at zero read it. */
  const [tally, setTally] = useState<Tally>({ answered: 0, closed: 0, skipped: 0 })
  const startedAt = useRef(Date.now())
  const [queueOpen, setQueueOpen] = useState(false)
  /** The store-wide re-check sheet. Closed on arrival: opening it takes a reading. */
  const [recheckOpen, setRecheckOpen] = useState(false)

  /* RUNS, FOLDED IN (D291). Open on arrival when the hash still carries
   * the intent a redirected `#/runs` link left behind — `?run=`, `?state=captured`,
   * `?box=`, or the bare `?runs=1` a link with none of those adds (`Runs.tsx:RunsRedirect`).
   * `RunsContent` itself reads the same three functions off the SAME hash to decide which
   * run opens or whether the composer does; this state is only whether the SHEET is up. */
  const [runsOpen, setRunsOpen] = useState(() => {
    const query = window.location.hash.split('?')[1] ?? ''
    return stateInHash() || runInHash() !== null || boxInHash() !== null || new URLSearchParams(query).get('runs') === '1'
  })

  /** True when the sheet was opened by the Identify strip, so it opens on the composer. */
  const [runsCompose, setRunsCompose] = useState(false)
  const openRuns = useCallback((compose: boolean) => {
    setRunsCompose(compose)
    setRunsOpen(true)
  }, [])
  const closeRuns = useCallback(() => setRunsOpen(false), [])

  /* THE STRIP: "Identify N cards, ~$X", drawn only when the pipeline has cards waiting
   * (`status.states.captured`, the same figure Home's own standing sentence reads). Two light
   * reads, not the composer's own preflight, which decodes every waiting photograph and takes
   * about a minute over five hundred cards. `~$X` is this store's own past cost per card
   * (`Runs.tsx:perCardRate`) times N. The press opens the composer, whose free preflight is the
   * real figure the spend is confirmed against, as it always was. */
  const [status, setStatus] = useState<ServerStatus | null>(null)
  const [rate, setRate] = useState<number | null>(null)
  useEffect(() => {
    let live = true
    void getStatus()
      .then((answer) => {
        if (live) setStatus(answer)
      })
      .catch(() => undefined)
    return () => {
      live = false
    }
  }, [reloads])
  const captured = status?.states.captured ?? 0
  /* The run list is read only when there is a strip to price: a store with nothing waiting
     pays for no second read. */
  const waiting = captured > 0
  useEffect(() => {
    if (!waiting) return
    let live = true
    void getRuns()
      .then((runs) => {
        if (live) setRate(perCardRate(runs))
      })
      .catch(() => undefined)
    return () => {
      live = false
    }
  }, [waiting, reloads])
  const about = rate === null ? null : rate * captured

  useEffect(() => {
    let live = true
    loadingRef.current = true
    setLoading(true)
    void getQueues()
      .then((snapshot) => {
        if (!live) return
        setRows(rowsOf(snapshot))
        setRefusal(null)
        setPhotoAbsent(null)
        setDeferred([])
      })
      .catch((err: unknown) => {
        if (!live) return
        setRows(null)
        setRefusal({ failure: describeFailure(err), at: null })
      })
      .finally(() => {
        if (!live) return
        loadingRef.current = false
        setLoading(false)
      })
    return () => {
      live = false
    }
  }, [reloads])

  /* The worklist: one row per position, skipped cards at the back in skip order, the
   * server's sort preserved inside the group that is left. `everyone` is the whole queue and
   * `worklist` is the lens over it. */
  const { everyone, worklist, allSkipped } = useMemo(() => {
    if (rows === null) return { everyone: [] as Row[], worklist: [] as Row[], allSkipped: false }
    const cards = oneCardPerPosition(rows)
    const skipped = new Set(deferred)
    const held = cards.filter((row) => !skipped.has(row.key))
    const byKey = new Map(cards.map((row) => [row.key, row]))
    const pushed = deferred.flatMap((key) => {
      const row = byKey.get(key)
      return row === undefined ? [] : [row]
    })
    const everyone = [...held, ...pushed]
    const match = (row: Row) => reasonFilter === null || row.entry.reason === reasonFilter
    const heldIn = held.filter(match)
    const pushedIn = pushed.filter(match)
    return { everyone, worklist: [...heldIn, ...pushedIn], allSkipped: heldIn.length === 0 && pushedIn.length > 0 }
  }, [rows, deferred, reasonFilter])

  const current = worklist[0] ?? null

  /* THE GROUP OFFER: THE LARGEST CLUSTER THE CARD IN FRONT OF YOU BELONGS TO, not the whole
   * worklist (D29, amended 2026-09-11).
   *
   * IT WAS ALL-OR-NOTHING UNTIL THEN, AND THAT IS WHAT KILLED IT IN PRACTICE. One card in
   * the list offering two rows returned null for every other card in it. Measured on the
   * owner's store the day this changed: their parked queue held 101 `rarity_claim_mismatch`
   * entries, 99 of them offering exactly one row of one condition (`Near Mint Foil`) — and
   * TWO offering two. Those two suppressed the button for ninety-nine, and the ninety-nine
   * were answered by hand, one press each.
   *
   * ANCHORED ON `worklist[0]`, WHICH IS THE CARD ON SCREEN. The alternative — the largest
   * cluster anywhere in the list — would offer to answer a group the operator is not
   * looking at, which is D29's own eligibility argument turned inside out: the press is
   * safe because the photographs on the confirm panel are the ones being answered.
   *
   * A `name_disputed` ENTRY IS NEVER IN A GROUP, even a uniform one. That reason exists
   * because the two things read off one photograph disagree, so the card is exactly the one
   * D29's "a claim about a set of cards nobody is looking at individually" must not sweep
   * up. It is also why the anchor is checked first: an operator standing ON a disputed card
   * is offered no group at all.
   *
   * THE SERVER'S CHECK IS AUTHORITATIVE AND THIS STAYS A SUBSET OF IT. Both sides cluster
   * on one reason, one row each, and one condition GRADE; anything this offers, the route
   * accepts.
   *
   * IT CLUSTERED ON THE CONDITION STRING UNTIL 2026-09-12, AND THAT SPLIT EVERY REAL QUEUE.
   * `Near Mint` and `Near Mint Foil` are one grade and two finishes, so a queue whose grade
   * D137 had already fixed by rule still arrived as two groups. Measured that day on the
   * owner's store: of 52 entries, 40 offered exactly one row and every one was Near Mint —
   * 21 plain, 19 foil — so the split was pure cost. Their words: *"i also somehow had to
   * still claim items in bulk that they're near mint rather than it being default."*
   *
   * `gradeOf` IS A STRING TEST HERE AND A REGISTRY LOOKUP ON THE SERVER, and the asymmetry
   * is deliberate because of which way it fails. The wire carries no game, so the client
   * cannot read `condition_by_finish`; a spelling this test does not recognise becomes its
   * own grade and simply is not grouped, which NARROWS the offer. The server, which can read
   * the registry, is the one that decides — so the client being conservative costs a press
   * and can never propose a group the route would refuse. */
  const groupOffer = useMemo((): { rows: Row[]; reason: string; left: number } | null => {
    const anchor = worklist[0]
    if (anchor === undefined) return null
    if (anchor.entry.reason === 'name_disputed') return null
    const only = anchor.entry.candidates[0]
    if (only === undefined || anchor.entry.candidates.length !== 1) return null
    const reason = anchor.entry.reason
    const grade = gradeOf(only.condition)
    const cluster = worklist.filter((row) => {
      if (row.entry.reason !== reason) return false
      const row_only = row.entry.candidates[0]
      return row_only !== undefined && row.entry.candidates.length === 1 && gradeOf(row_only.condition) === grade
    })
    if (cluster.length < 2) return null
    return { rows: cluster, reason, left: worklist.length - cluster.length }
  }, [worklist])

  useEffect(() => {
    if (grouping && groupOffer === null) setGrouping(false)
  }, [grouping, groupOffer])

  /* The close panel never survives the card it was raised for. */
  const currentKey = current?.key ?? null
  useEffect(() => {
    setClosing(false)
  }, [currentKey])

  const putBack = useCallback((back: Row[], at: number) => {
    if (back.length === 0) return
    setRows((prev) => {
      if (prev === null) return [...back]
      const next = [...prev]
      next.splice(at < 0 ? 0 : Math.min(at, next.length), 0, ...back)
      return next
    })
  }, [])

  const remember = useCallback((receipt: Receipt) => {
    setReceipts((held) => [receipt, ...held.filter((standing) => standing.key !== receipt.key)].slice(0, UNDO_DEPTH))
  }, [])

  const count = useCallback((field: 'answered' | 'closed' | 'skipped', by: number) => {
    setTally((prev) => ({ ...prev, [field]: Math.max(0, prev[field] + by) }))
  }, [])

  /* Close a card without answering it (D37 stand-down, D26 retirement). Not optimistic: the
   * row leaves only once the server has confirmed. */
  const closeCard = useCallback(
    (row: Row, how: CloseChoice) => {
      if (busyRef.current || loadingRef.current) return
      const position = row.entry.position
      const at = rows === null ? -1 : rows.findIndex((held) => held.entry.position === position)
      const dropped = rows === null ? [row] : rows.filter((held) => held.entry.position === position)

      busyRef.current = true
      setBusy(true)
      setRefusal(null)
      setClosing(false)

      const call = how.kind === 'stand_down' ? standDown(row.entry.box, row.entry.index, how.reason) : retireCard(row.entry.box, row.entry.index, how.reason)

      void call
        .then((result: unknown) => {
          setRows((prev) => (prev === null ? prev : prev.filter((held) => held.entry.position !== position)))
          count('closed', 1)
          const reversible = how.kind === 'stand_down' || (result as { restores_to?: unknown } | null)?.restores_to != null
          /* UX-205: the receipt is unconditional. Only the Undo control depends on
             `reversible` — a stand-down is always reversible; a retirement is only when the
             server hands back a `restores_to`. */
          remember({
            key: position,
            reverse: how.kind === 'stand_down' ? undoStandDown : undoRetire,
            targets: [{ box: row.entry.box, index: row.entry.index, position, label: row.entry.label }],
            label: row.entry.label,
            dropped,
            at,
            said: 'Closed',
            outcome: how.kind === 'stand_down' ? 'left in place' : 'retired',
            counts: 'closed',
            undoable: reversible,
          })
        })
        .catch((err: unknown) => {
          setRefusal({ failure: describeFailure(err), at: row.entry.label })
        })
        .finally(() => {
          busyRef.current = false
          setBusy(false)
        })
    },
    [rows, remember, count],
  )

  /* Answer: advance first, write, put the card back if the write fails — except for the
   * stale codes, which are never restored. */
  const answer = useCallback(
    (row: Row, candidate: CandidateRow, fromCatalog = false) => {
      if (busyRef.current || loadingRef.current) return
      const position = row.entry.position
      const dropped = rows === null ? [row] : rows.filter((held) => held.entry.position === position)
      const at = rows === null ? -1 : rows.findIndex((held) => held.entry.position === position)
      busyRef.current = true
      setBusy(true)
      setRefusal(null)
      setRows((prev) => (prev === null ? prev : prev.filter((held) => held.entry.position !== position)))

      const restore = (back: Row[]) => putBack(back, at)

      void answerReview({
        box: row.entry.box,
        index: row.entry.index,
        sku: candidate.sku,
        condition: candidate.condition,
        fromCatalog,
      })
        .then((result: unknown) => {
          const cleared = clearedQueues(result)
          const kept = cleared === null ? [] : dropped.filter((held) => !cleared.has(held.queue))
          if (kept.length > 0) restore(kept)
          if (kept.length === 0) count('answered', 1)

          /* UX-205: the receipt is unconditional — every write it advances gets one, so the
             session list is never silently short of what the operator did. Only Undo depends
             on `canTakeBack`. */
          if (kept.length === 0) {
            remember({
              key: position,
              reverse: undoAnswer,
              targets: [{ box: row.entry.box, index: row.entry.index, position, label: row.entry.label }],
              label: row.entry.label,
              dropped,
              at,
              said: `Answered as ${candidate.condition}`,
              counts: 'answered',
              undoable: canTakeBack(result as AnswerResult),
            })
          }

          const answered = new Set(dropped.map((held) => held.key))
          setDeferred((prev) => (prev.some((key) => answered.has(key)) ? prev.filter((key) => !answered.has(key)) : prev))
        })
        .catch((err: unknown) => {
          if (!isStale(err)) restore(dropped)
          setRefusal({ failure: describeFailure(err), at: row.entry.label })
        })
        .finally(() => {
          busyRef.current = false
          setBusy(false)
        })
    },
    [rows, putBack, remember, count],
  )

  /* Take one answer back (D28). Waits for the server; walks a group one position at a time. */
  const undo = useCallback(
    (receipt: Receipt) => {
      if (busyRef.current || loadingRef.current) return
      busyRef.current = true
      setBusy(true)
      setRefusal(null)

      const walk = async () => {
        const reversed: string[] = []
        const finished: string[] = []
        const failures: { label: string; failure: Failure }[] = []
        for (const target of receipt.targets) {
          try {
            await receipt.reverse(target.box, target.index)
            reversed.push(target.position)
          } catch (err: unknown) {
            failures.push({ label: target.label, failure: describeFailure(err) })
            if (isFinalRefusal(err)) {
              finished.push(target.position)
              continue
            }
            break
          }
        }
        return { reversed, finished, failures }
      }

      void walk()
        .then(({ reversed, finished, failures }) => {
          const done = new Set([...reversed, ...finished])
          const back = receipt.dropped.filter((row) => reversed.includes(row.entry.position))
          if (back.length > 0) putBack(back, receipt.at)
          if (reversed.length > 0) count(receipt.counts, -new Set(reversed).size)

          setReceipts((held) =>
            held.flatMap((standing) => {
              if (standing.key !== receipt.key) return [standing]
              const targets = standing.targets.filter((target) => !done.has(target.position))
              const first = targets[0]
              if (first === undefined) return []
              return [
                {
                  ...standing,
                  targets,
                  dropped: standing.dropped.filter((row) => !done.has(row.entry.position)),
                  label: targets.length === 1 ? first.label : `${targets.length} still answered`,
                },
              ]
            }),
          )

          const [first] = failures
          if (first !== undefined && failures.length === 1) {
            setRefusal({ failure: first.failure, at: first.label })
          } else if (failures.length > 1) {
            setRefusal({
              failure: {
                code: 'group_undo_incomplete',
                message: failures.map(({ label, failure }) => `${label}: ${failure.message}`).join(' '),
              },
              at: null,
            })
          }
        })
        .catch((err: unknown) => {
          setRefusal({ failure: describeFailure(err), at: receipt.label })
        })
        .finally(() => {
          busyRef.current = false
          setBusy(false)
        })
    },
    [putBack, count],
  )

  /* The group write: one route call, nothing dropped until the server answers. */
  const answerGroup = useCallback(() => {
    if (busyRef.current || loadingRef.current) return
    const offer = groupOffer
    if (offer === null || rows === null) return

    const positions = new Set(offer.rows.map((row) => row.entry.position))
    const labels = new Map(offer.rows.map((row) => [row.entry.position, row.entry.label]))

    busyRef.current = true
    setBusy(true)
    setRefusal(null)

    void answerReviewGroup(
      offer.rows.map((row) => ({
        box: row.entry.box,
        index: row.entry.index,
        sku: row.entry.candidates[0]?.sku ?? '',
        condition: row.entry.candidates[0]?.condition ?? '',
      })),
    )
      .then((result) => {
        const byPosition = new Map(result.results.map((member) => [member.position, member]))
        const clearedRow = (row: Row): boolean => {
          const member = byPosition.get(row.entry.position)
          if (member === undefined) return false
          return row.queue === 'review' ? member.review_cleared : member.parked_cleared
        }
        const dropped = rows.filter(clearedRow)
        const at = rows.findIndex(clearedRow)
        setRows((prev) => (prev === null ? prev : prev.filter((row) => !clearedRow(row))))
        count('answered', new Set(dropped.map((row) => row.entry.position)).size)

        /* UX-205: the receipt is unconditional, as it is for a single answer above. Undo
           still needs EVERY member reversible — a partial undo would leave the group split
           between two states with no way to tell which is which. */
        const reversible = result.results.every((member) => member.restores_to !== null)
        if (dropped.length > 0) {
          remember({
            key: result.answered.join('+'),
            reverse: undoAnswer,
            targets: result.results.map((member) => ({
              box: member.box,
              index: member.index,
              position: member.position,
              label: labels.get(member.position) ?? member.position,
            })),
            label: `${result.count} cards ${result.reason}`,
            dropped,
            at,
            said: `Answered all ${result.count} together`,
            counts: 'answered',
            undoable: reversible,
          })
        }

        const answered = new Set(dropped.map((row) => row.key))
        setDeferred((prev) => (prev.some((key) => answered.has(key)) ? prev.filter((key) => !answered.has(key)) : prev))
        setGrouping(false)
        setReasonFilter(null)
      })
      .catch((err: unknown) => {
        setRefusal({ failure: describeFailure(err), at: `${positions.size} cards` })
      })
      .finally(() => {
        busyRef.current = false
        setBusy(false)
      })
  }, [groupOffer, rows, remember, count])

  const skip = useCallback(
    (row: Row) => {
      setDeferred((prev) => [...prev.filter((key) => key !== row.key), row.key])
      count('skipped', 1)
    },
    [count],
  )

  const clearSkips = useCallback(() => setDeferred([]), [])
  const reload = useCallback(() => setReloads((n) => n + 1), [])
  /* Stable, because the sheet re-previews whenever `open` goes true and a new identity for
     either prop would be a second reading of the store on the same opening. */
  const closeRecheck = useCallback(() => setRecheckOpen(false), [])

  /* D46/D77: the export's rows, unasked for a zero-candidate card and on `L` for one with rows. */
  const looking = current !== null && lookingAt === current.key
  const showCatalog = current !== null && (current.entry.candidates.length === 0 || looking)
  const lookupFor = showCatalog ? current : null
  const lookupKey = lookupFor === null ? '' : lookupFor.key
  useEffect(() => {
    setLookup(null)
    setLookupFailed(null)
    setTyped('')
    if (lookupFor === null) return
    let canceled = false
    void reviewCatalog(lookupFor.entry.box, lookupFor.entry.index, '')
      .then((answer) => {
        if (!canceled) setLookup(answer)
      })
      .catch((err: unknown) => {
        if (!canceled) setLookupFailed(describeFailure(err).message)
      })
    return () => {
      canceled = true
    }
    // `lookupKey` rather than the row object, which is rebuilt on every read; `looking` is
    // the second dependency because pressing L does not change the key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lookupKey, looking])

  const searchCatalog = useCallback(
    (query: string) => {
      if (current === null) return
      setLookupFailed(null)
      void reviewCatalog(current.entry.box, current.entry.index, query)
        .then(setLookup)
        .catch((err: unknown) => setLookupFailed(describeFailure(err).message))
    },
    [current],
  )

  /* The next card's photograph, fetched while this one is judged (D28). One card ahead. */
  const nextPhoto = useMemo(() => {
    const next = worklist[1]
    if (next === undefined) return null
    if (next.entry.box < 1 || next.entry.photo === null) return null
    /* The slot route, for `QueuePhoto`'s reason below: a queue entry carries no `cid`. The
       prefetch must address the photograph exactly as the render will, or it warms a URL
       nothing asks for. */
    return photoUrl(next.entry.box, next.entry.index)
  }, [worklist])

  useEffect(() => {
    if (nextPhoto === null) return
    const warm = new Image()
    warm.src = nextPhoto
    return () => {
      warm.src = ''
    }
  }, [nextPhoto])

  /* The key map. R and U are armed with no card on screen; the group state and the close
   * panel own the keyboard while they are up; the digits read whichever list is drawn. */
  /* THE KEYBOARD, BUILT EVERY RENDER AND REGISTERED ONCE.
   *
   * It used to be built INSIDE an effect keyed on sixteen values, so every one of them
   * swapped the window listener — and between a state change and the effect that follows it,
   * the listener on the window still closed over the PREVIOUS values. A digit pressed in that
   * gap (measured: about one run in four, right after the catalog rows paint) read the old
   * candidate list, found nothing at that position, and returned. No answer, no refusal, no
   * mark on screen: the press was swallowed. On the screen the operator spends the most hours
   * in, answering one card per keystroke, a silently dropped answer is the worst failure this
   * component has.
   *
   * So the handler is an ordinary function created during render — it closes over this
   * render's values by construction — and a ref carries the newest one to a listener that is
   * registered exactly once. `handlerRef.current` is assigned during render rather than in an
   * effect on purpose: an effect runs AFTER paint, which is the very window this bug lived in. */
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.repeat) return
    if (event.metaKey || event.ctrlKey || event.altKey) return
    if (isEditableTarget(event.target)) return
    if (busyRef.current || loadingRef.current) return

    /* THE RE-CHECK SHEET OWNS THE KEYBOARD WHILE IT IS UP, which is the rule the close panel
     * and the group state already follow. Every key below answers, closes, skips or reloads
     * the card behind the scrim — a digit pressed at this sheet would list a card the
     * operator cannot see. Escape is the sheet's own, through `useOverlayFocus`. */
    if (recheckOpen) return

    const key = event.key.toLowerCase()

    if (key === RELOAD_KEY) {
      event.preventDefault()
      reload()
      return
    }

    if (key === UNDO_KEY) {
      const newest = receipts[0]
      if (newest === undefined) return
      event.preventDefault()
      undo(newest)
      return
    }

    if (grouping && groupOffer !== null) {
      if (key === 'enter') {
        event.preventDefault()
        answerGroup()
        return
      }
      if (key === 'escape') {
        event.preventDefault()
        setGrouping(false)
        return
      }
      return
    }

    if (key === GROUP_KEY && groupOffer !== null) {
      event.preventDefault()
      setGrouping(true)
      return
    }

    if (current === null) return

    if (closing) {
      if (key === 'escape') {
        event.preventDefault()
        setClosing(false)
        return
      }
      const pick = Number(key)
      const chosen = CLOSE_CHOICES[pick - 1]
      if (Number.isInteger(pick) && chosen !== undefined) {
        event.preventDefault()
        closeCard(current, chosen.choice)
      }
      return
    }

    if (key === CLOSE_KEY) {
      event.preventDefault()
      setClosing(true)
      return
    }

    if (key === LOOKUP_KEY && current.entry.candidates.length > 0) {
      event.preventDefault()
      setLookingAt(looking ? null : current.key)
      return
    }

    if (key === 'escape' && looking) {
      event.preventDefault()
      setLookingAt(null)
      return
    }

    if (key === SKIP_KEY) {
      event.preventDefault()
      skip(current)
      return
    }

    if (key === CLEAR_KEY && allSkipped) {
      event.preventDefault()
      clearSkips()
      return
    }

    const digit = Number(key)
    if (!Number.isInteger(digit) || digit < 1 || digit > MAX_KEYED_CANDIDATES) return
    const candidate = showCatalog ? (lookup?.rows ?? [])[digit - 1] : current.entry.candidates[digit - 1]
    if (candidate === undefined) return
    event.preventDefault()
    answer(current, candidate, showCatalog)
  }


  const handlerRef = useRef(onKeyDown)
  handlerRef.current = onKeyDown
  useEffect(() => {
    const fire = (event: KeyboardEvent) => handlerRef.current(event)
    window.addEventListener('keydown', fire)
    return () => window.removeEventListener('keydown', fire)
  }, [])

  /* The queue drawer closes on Escape. Its own listener: it is chrome, not a state that
   * owns the keyboard, so every other Escape still does what it did. */
  useEffect(() => {
    if (!queueOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setQueueOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [queueOpen])

  const counts = useMemo(() => {
    if (rows === null) return null
    return {
      review: rows.filter((row) => row.queue === 'review').length,
      parked: rows.filter((row) => row.queue === 'parked').length,
    }
  }, [rows])

  /* The newest receipt stands beside the rows for twenty seconds, then settles into the
   * session list. The receipt itself is not expiring — only its place on screen is. */
  const newestKey = receipts[0]?.key ?? null
  const [trayKey, setTrayKey] = useState<string | null>(null)
  useEffect(() => {
    if (newestKey === null) return
    setTrayKey(newestKey)
    const timer = window.setTimeout(() => setTrayKey((held) => (held === newestKey ? null : held)), RECEIPT_TRAY_MS)
    return () => window.clearTimeout(timer)
  }, [newestKey])
  const trayReceipt = trayKey === null ? null : (receipts.find((receipt) => receipt.key === trayKey) ?? null)

  /* The reason lens, in a FIXED order: by label, so a chip the operator reaches for by
   * position stays where it was after every answer. Only the count badge moves. */
  const shape = useMemo(() => {
    const tallies = new Map<string, number>()
    for (const row of everyone) tallies.set(row.entry.reason, (tallies.get(row.entry.reason) ?? 0) + 1)
    return [...tallies].sort((a, b) => reasonLabel(a[0]).localeCompare(reasonLabel(b[0])) || a[0].localeCompare(b[0]))
  }, [everyone])
  const lens = shape.length > 1 || reasonFilter !== null

  const done = tally.answered + tally.closed
  const total = everyone.length + done
  const progress = total === 0 ? 0 : Math.min(1, done / total)
  const disabled = busy || loading
  const activity = busy ? 'Writing…' : loading ? 'Reading the queues…' : null

  const tray = (
    <Tray
      receipt={trayReceipt}
      refusal={refusal}
      onUndo={undo}
      onReload={reload}
      onDismiss={() => setRefusal(null)}
      allSkipped={allSkipped}
      onClearSkips={clearSkips}
      disabled={disabled}
    />
  )

  return (
    <Page
      className={['review', queueOpen ? 'is-queue-open' : '', lens ? 'review-pagehead has-lens' : 'review-pagehead'].filter(Boolean).join(' ')}
      icon="inbox"
      title="Review"
      lede={
        <span className="review-progress" aria-live="polite">
          <span className="review-progress-text bn-tnum">
            {rows === null ? (
              loading ? (
                'Reading the queues…'
              ) : (
                'The queues did not load.'
              )
            ) : total === 0 ? (
              'Nothing is waiting.'
            ) : (
              /* UX-256: one count, not two that can differ by one. "to go" is
                 `everyone.length`, the same number the Queue button's own badge shows
                 (D164's counter), so the two never disagree again. */
              <>
                <strong>{done}</strong> done, <strong>{everyone.length}</strong> to go
              </>
            )}
            {counts !== null && counts.parked > 0 ? <span className="review-progress-parked">{counts.parked} parked</span> : null}
          </span>
          {total === 0 ? null : (
            <span className="bn-progress review-progress-bar" aria-hidden="true">
              <span style={{ width: `${Math.round(progress * 100)}%` }} />
            </span>
          )}
        </span>
      }
      actions={
        <>
          {groupOffer === null || grouping ? null : (
            <Button icon="layers" kbd={GROUP_KEY_LABEL} onClick={() => setGrouping(true)} disabled={disabled}>
              Answer all {groupOffer.rows.length} together
            </Button>
          )}
          {/* The header rule (owner, 2026-09-24): one worded primary. "Answer all N
              together" is it, when a group offer is on screen — the rest are icons. NOT
              THE RELOAD BESIDE IT: one re-fetches these two queues, this one asks the
              pipeline to look at every waiting card again. Same icon vocabulary word would
              make them read as one control, so the tooltip keeps the fuller sentence. */}
          <IconButton icon="wand" label="Re-check every waiting card" onClick={() => setRecheckOpen(true)} disabled={disabled} className="review-recheck-open" />
          {/* The kit's own reload control (D288), with its internal 'r' hotkey
              OFF: this screen wires RELOAD_KEY into the same switch every other key rides,
              because a second listener would fire the read twice. */}
          <ReloadButton onReload={reload} busy={disabled} label="Reload the queue" hotkey={false} className="review-reload" />
          {/* D291: past runs, and every other Runs capability, behind one link. */}
          <IconButton icon="history" label="Past runs" onClick={() => openRuns(false)} className="review-runs-open" />
          {everyone.length === 0 ? null : (
            <IconButton
              icon="list"
              label="Queue"
              /* The badge is aria-hidden (D118), so the count reaches a screen reader
                 through `name` only — the same pattern `kit/filters.tsx`'s own trigger
                 uses for its active-facet count. */
              name={`Queue, ${everyone.length}`}
              badge={everyone.length}
              onClick={() => setQueueOpen(true)}
              className="review-queue-toggle"
              aria-expanded={queueOpen}
            />
          )}
        </>
      }
    >
      {/* THE STRIP (D291): drawn only when the pipeline has cards waiting. One sentence and
          one worded press, because it spends money. It opens the composer on its default
          "needed" start, every card photographed and not identified, which is this N. */}
      {captured === 0 ? null : (
        <div className="review-identify-strip">
          <span className="review-identify-strip-said">
            <Icon name="camera" size={16} />
            Photographed, not yet identified.
          </span>
          <Button icon="zap" onClick={() => openRuns(true)} className="review-identify-open">
            Identify {captured} {captured === 1 ? 'card' : 'cards'}
            {about === null ? null : roundsToNothing(about) ? ', under a cent' : (
              <>
                , ~<Money value={about} />
              </>
            )}
          </Button>
        </div>
      )}

      {!lens ? null : (
        <div className="review-filters" role="group" aria-label="Work one reason at a time">
          {shape.map(([reason, n]) => (
            <button
              key={reason}
              type="button"
              className="review-filter"
              aria-pressed={reasonFilter === reason}
              title={reason}
              onClick={() => setReasonFilter(reasonFilter === reason ? null : reason)}
              disabled={disabled}
            >
              <span className="review-filter-label">{reasonLabel(reason)}</span>
              <span className="review-filter-count">{n}</span>
            </button>
          ))}
          {reasonFilter === null ? null : (
            <button type="button" className="review-filter review-filter-clear" onClick={() => setReasonFilter(null)} disabled={disabled}>
              <Icon name="x" size={12} />
              Every reason
            </button>
          )}
        </div>
      )}

      {current === null && refusal !== null ? (
        <div className="review-lone">
          <RefusalNotice refusal={refusal} onReload={reload} onDismiss={() => setRefusal(null)} disabled={disabled} />
        </div>
      ) : null}

      {rows === null && refusal === null ? <LoadingCard /> : null}

      {rows !== null && worklist.length === 0 ? (
        everyone.length === 0 ? (
          <Done tally={tally} startedAt={startedAt.current} receipts={receipts} onUndo={undo} disabled={disabled} onOpenRuns={() => openRuns(false)} />
        ) : (
          <section className="review-lone bn-panel">
            <EmptyState
              icon="filter"
              title="Nothing waiting for this reason"
              body={`${everyone.length} other ${everyone.length === 1 ? 'card is' : 'cards are'} still queued behind the filter. Nothing was written to them.`}
              actions={
                <Button variant="primary" icon="x" onClick={() => setReasonFilter(null)} disabled={disabled}>
                  Show every reason
                </Button>
              }
            />
          </section>
        )
      ) : null}

      <div className="review-body">
        {current === null ? null : grouping && groupOffer !== null ? (
          <GroupConfirm offer={groupOffer} activity={activity} onConfirm={answerGroup} onLeave={() => setGrouping(false)} tray={tray} />
        ) : (
          <Card
            row={current}
            next={worklist[1] ?? null}
            phone={phone}
            activity={activity}
            photoAbsent={photoAbsent === current.key}
            onPhotoAbsent={() => setPhotoAbsent(current.key)}
            onChoose={(candidate) => answer(current, candidate)}
            onSkip={() => skip(current)}
            lookup={lookup}
            lookupFailed={lookupFailed}
            typed={typed}
            onTyped={setTyped}
            onSearch={() => searchCatalog(typed)}
            onChooseCatalog={(row) => answer(current, row, true)}
            showCatalog={showCatalog}
            looking={looking}
            onLookup={() => setLookingAt(looking ? null : current.key)}
            onClose={() => setClosing((up) => !up)}
            closing={closing}
            onCloseChoice={(choice) => closeCard(current, choice)}
            tray={tray}
          />
        )}

        {everyone.length === 0 ? null : (
          <>
            {queueOpen ? <div className="bn-scrim review-rail-scrim" onClick={() => setQueueOpen(false)} aria-hidden="true" /> : null}
            <Waiting
              rows={everyone}
              currentKey={current?.key ?? null}
              deferred={deferred}
              filter={reasonFilter}
              tally={tally}
              receipts={receipts}
              onUndo={undo}
              onClose={() => setQueueOpen(false)}
              disabled={disabled}
            />
          </>
        )}
      </div>

      <QueueRefresh open={recheckOpen} onClose={closeRecheck} onWrote={reload} />

      {/* D291: every Runs capability, reachable from here. Mounted only
          while open (`Sheet`'s own `useLeave`), so its GET /boxes and GET /pipeline/runs
          reads happen only when the operator is looking at it. */}
      <Sheet open={runsOpen} onClose={closeRuns} title="Runs" icon="history" className="review-runs-sheet">
        <RunsContent compose={runsCompose} onLeave={closeRuns} />
      </Sheet>
    </Page>
  )
}

// ------------------------------------------------------------------------------ the tray

/* What just happened, drawn in a reserved slot under the actions so nothing above it moves:
 * the newest receipt with its undo, a refusal with its remedy, the end of the skip loop. */
function Tray({
  receipt,
  refusal,
  onUndo,
  onReload,
  onDismiss,
  allSkipped,
  onClearSkips,
  disabled,
}: {
  receipt: Receipt | null
  refusal: Refusal | null
  onUndo: (receipt: Receipt) => void
  onReload: () => void
  onDismiss: () => void
  allSkipped: boolean
  onClearSkips: () => void
  disabled: boolean
}) {
  return (
    <div className="review-tray">
      {refusal === null ? null : <RefusalNotice refusal={refusal} onReload={onReload} onDismiss={onDismiss} disabled={disabled} />}
      {!allSkipped ? null : (
        <Notice tone="info" title="Every waiting card has been skipped" className="review-tray-notice">
          Skipping again only moves this one behind the rest.{' '}
          {/* words="word-only-control" (rule 5): a press inside a sentence. */}
          <Button size="sm" variant="quiet" kbd={CLEAR_KEY_LABEL} onClick={onClearSkips} disabled={disabled} words="word-only-control">
            Clear skips
          </Button>
        </Notice>
      )}
      {receipt === null ? null : (
        <div className="bn-receipt review-note review-receipt" role="status" key={receipt.key} style={{ ['--receipt-ms' as string]: `${RECEIPT_TRAY_MS}ms` }}>
          <Icon name="check" size={16} className="review-receipt-icon" />
          <span className="review-receipt-text">
            <span className="review-receipt-said">{receipt.said}</span>
            <span className="review-receipt-label">{receipt.label}</span>
            {/* UX-255: the outcome, as a description beside the one act-verb — never a
                second verb competing with "Closed". */}
            {receipt.outcome === undefined ? null : <span className="review-receipt-outcome">{receipt.outcome}</span>}
          </span>
          <span className="bn-receipt-bar" aria-hidden="true" />
          {!receipt.undoable ? null : (
            <IconButton icon="undo" label="Undo" size="sm" kbd={UNDO_KEY_LABEL} onClick={() => onUndo(receipt)} disabled={disabled} />
          )}
        </div>
      )}
    </div>
  )
}

function RefusalNotice({ refusal, onReload, onDismiss, disabled }: { refusal: Refusal; onReload: () => void; onDismiss: () => void; disabled: boolean }) {
  const stale = STALE_CODES.has(refusal.failure.code)
  return (
    <Notice tone="danger" title={refusal.failure.message} code={`${refusal.failure.code}${refusal.at === null ? '' : ` ${refusal.at}`}`} className="review-refusal review-note">
      <span className="review-refusal-actions">
        {/* ICON-MAP (review): words, not an icon — this is the notice's own recovery, the
            one primary action beside Dismiss. words="only-primary" (rule 4). */}
        {stale ? (
          <Button size="sm" icon="refresh" kbd={RELOAD_KEY_LABEL} onClick={onReload} disabled={disabled} words="only-primary">
            Reload the queue
          </Button>
        ) : null}
        <IconButton icon="x" label="Dismiss" size="sm" onClick={onDismiss} />
      </span>
    </Notice>
  )
}

/* The session's receipts as compact rows. The newest carries the key; older ones are pressed. */
function SessionList({ receipts, onUndo, disabled, limit }: { receipts: readonly Receipt[]; onUndo: (receipt: Receipt) => void; disabled: boolean; limit?: number }) {
  const [expanded, setExpanded] = useState(false)
  const shown = limit === undefined || expanded ? receipts : receipts.slice(0, limit)
  const hidden = receipts.length - shown.length
  if (receipts.length === 0) return null
  return (
    <ul className="review-session-list">
      {shown.map((receipt, at) => (
        <li key={receipt.key} className="review-session-row">
          <Icon name="check" size={14} className="review-session-icon" />
          <span className="review-session-text">
            <span className="review-session-said">{receipt.said}</span>
            <span className="review-session-label">{receipt.label}</span>
            {receipt.outcome === undefined ? null : <span className="review-session-outcome">{receipt.outcome}</span>}
          </span>
          {!receipt.undoable ? null : (
            <IconButton icon="undo" label="Undo" size="sm" kbd={at === 0 ? UNDO_KEY_LABEL : undefined} onClick={() => onUndo(receipt)} disabled={disabled} />
          )}
        </li>
      ))}
      {hidden > 0 ? (
        <li>
          <button type="button" className="review-session-more" onClick={() => setExpanded(true)}>
            {hidden} more
          </button>
        </li>
      ) : null}
    </ul>
  )
}

// ------------------------------------------------------------------------- the empty state

function Done({
  tally,
  startedAt,
  receipts,
  onUndo,
  disabled,
  onOpenRuns,
}: {
  tally: Tally
  startedAt: number
  receipts: readonly Receipt[]
  onUndo: (receipt: Receipt) => void
  disabled: boolean
  onOpenRuns: () => void
}) {
  const done = tally.answered + tally.closed
  const body =
    done === 0 ? (
      'When a run leaves a card in doubt, it lands here for one answer.'
    ) : (
      <>
        {`You answered ${tally.answered} ${tally.answered === 1 ? 'card' : 'cards'} in ${durationText(Date.now() - startedAt)}`}
        {tally.closed > 0 ? <span className="review-done-tally">{tally.closed} closed</span> : null}
        {tally.skipped > 0 ? <span className="review-done-tally">{tally.skipped} skipped</span> : null}.
      </>
    )
  return (
    <section className="review-done bn-panel">
      <EmptyState
        icon="check"
        className="review-done-empty"
        title="All caught up."
        body={body}
        actions={
          <>
            <Button variant="primary" size="lg" icon="tag" iconRight="arrowRight" onClick={() => (window.location.hash = '#/pricing')}>
              Price the answers
            </Button>
            <Button size="lg" icon="play" onClick={onOpenRuns}>
              Run another box
            </Button>
          </>
        }
      />
      {receipts.length === 0 ? null : (
        <div className="review-done-session">
          <div className="bn-rule">This session</div>
          <SessionList receipts={receipts} onUndo={onUndo} disabled={disabled} limit={3} />
        </div>
      )}
    </section>
  )
}

function LoadingCard() {
  return (
    <div className="review-body">
      <section className="review-card is-loading" aria-busy="true">
        <div className="review-stage">
          <div className="review-frame review-well" />
        </div>
        <div className="review-verdict">
          <div className="bn-skeleton" style={{ height: 26, width: '52%' }} />
          <div className="bn-skeleton" style={{ height: 14, width: '34%', marginTop: 8 }} />
          <div className="bn-skeleton" style={{ height: 22, width: '60%', marginTop: 18 }} />
          <div className="review-candidates" style={{ marginTop: 20 }}>
            {[0, 1, 2].map((i) => (
              <div key={i} className="bn-skeleton review-candidate-skeleton" />
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}

// ------------------------------------------------------------------------------ the group

function GroupConfirm({
  offer,
  activity,
  onConfirm,
  onLeave,
  tray,
}: {
  offer: { rows: Row[]; reason: string; left: number }
  activity: string | null
  onConfirm: () => void
  onLeave: () => void
  tray: ReactNode
}) {
  const busy = activity !== null
  const [absent, setAbsent] = useState<ReadonlySet<string>>(new Set())

  return (
    <section className="review-group bn-anim-in">
      <header className="review-group-head">
        <div className="review-question">
          {/* THE GRADE IS NOT WHAT IS BEING ASKED, AND THE HEADLINE SAID IT WAS UNTIL
              2026-09-12. `Answer all 27 as Near Mint Foil?` put a word D137 fixes by rule
              where the question should be, and the operator read it as a claim they were
              being made to enter by hand: *"i also somehow had to still claim items in bulk
              that they're near mint rather than it being default."* The question is whether
              these cards are each their own single row; the grade is a property of the
              catalogue, and it is stated below as context rather than asked here. */}
          <h2 className="review-question-title">Answer all {offer.rows.length} together?</h2>
          {/* The pipeline's own reason code (`set_ambiguous` and the like) is a debugging
              fact, not something a person doing this work needs to read or find — the
              sentence already says it in plain English, and a `title` is unreliable for a
              screen reader and unreachable by touch besides. Gone means gone; a raw code
              wanted for debugging belongs in a log, not in this markup. */}
          <p className="review-question-sub">{reasonLabel(offer.reason)}</p>
        </div>
        <p className="review-sentence">
          Each card offers one row, for the same reason. One press answers each with its own row — the finish it was sorted and photographed as, all <span className="review-claim">Near Mint</span>, the catalogue's only grade.
        </p>
        {/* WHAT THE PRESS IS NOT ANSWERING FOR. The group is a cluster rather than the whole
            worklist, so the operator has to be told the rest is still theirs — an unstated
            remainder reads as "the queue is done" and is the one way this control can
            mislead. Silent when it answers everything. */}
        {offer.left === 0 ? null : (
          <p className="review-sentence review-group-left">
            {offer.left} more {offer.left === 1 ? 'card is' : 'cards are'} still in this list and will not be
            answered — {offer.left === 1 ? 'it offers' : 'they offer'} a different row, grade or reason.
          </p>
        )}
      </header>

      <ul className="review-group-grid">
        {offer.rows.map((row, at) => (
          <li key={row.key} className="review-group-cell" style={{ animationDelay: `${Math.min(at, 24) * 25}ms` }}>
            {row.entry.box < 1 || row.entry.photo === null || absent.has(row.key) ? (
              <span className="review-group-absent">
                <Icon name="image" size={18} />
                no photo
              </span>
            ) : (
              <img
                className="review-group-photo"
                /* The slot route again, and for the same reason: these are queue entries
                   (D29's homogeneous group), which carry no `cid`. */
                src={photoUrl(row.entry.box, row.entry.index)}
                alt={`The card photographed at ${row.entry.label}`}
                loading="lazy"
                onError={() =>
                  setAbsent((prev) => {
                    const next = new Set(prev)
                    next.add(row.key)
                    return next
                  })
                }
              />
            )}
            <span className="review-group-pos">
              <PositionLabel label={row.entry.label} flow="run" />
            </span>
          </li>
        ))}
      </ul>

      <div className="review-group-bar">
        <button className="bn-btn bn-btn-primary bn-btn-lg review-group-confirm" type="button" onClick={onConfirm} disabled={busy}>
          <Icon name="check" size={16} />
          Answer all {offer.rows.length} together
          <Kbd>↵</Kbd>
        </button>
        <Button variant="ghost" size="lg" icon="arrowLeft" kbd="Esc" onClick={onLeave} disabled={busy}>
          One at a time
        </Button>
        {activity === null ? null : <Busy activity={activity} />}
      </div>

      {tray}
    </section>
  )
}

function Busy({ activity }: { activity: string }) {
  return (
    <span className="review-busy" role="status">
      <span className="review-spinner" aria-hidden="true" />
      {activity}
    </span>
  )
}

// ------------------------------------------------------------------------------- the card

type CardProps = {
  row: Row
  next: Row | null
  phone: boolean
  activity: string | null
  photoAbsent: boolean
  onPhotoAbsent: () => void
  onChoose: (candidate: CandidateRow) => void
  onSkip: () => void
  lookup: CatalogLookup | null
  lookupFailed: string | null
  typed: string
  onTyped: (text: string) => void
  onSearch: () => void
  onChooseCatalog: (row: CandidateRow) => void
  showCatalog: boolean
  looking: boolean
  onLookup: () => void
  onClose: () => void
  closing: boolean
  onCloseChoice: (choice: CloseChoice) => void
  tray: ReactNode
}

function Card({
  row,
  next,
  phone,
  activity,
  photoAbsent,
  onPhotoAbsent,
  onChoose,
  onSkip,
  lookup,
  lookupFailed,
  typed,
  onTyped,
  onSearch,
  onChooseCatalog,
  showCatalog,
  looking,
  onLookup,
  onClose,
  closing,
  onCloseChoice,
  tray,
}: CardProps) {
  const { entry } = row
  const parts = sentence(entry)
  const busy = activity !== null
  const claims = claimsOf(entry)
  const head = showCatalog ? null : sharedHead(entry.candidates)
  /* The one reason whose chips restated its own sentence was the finish disagreement, and
   * the sentence was hidden under them. That reason is retired, so every card draws its
   * sentence and nothing is conditional on which one it is. */
  const retired = isRetiredReason(entry.reason)

  return (
    <section className="review-card">
      <div className="review-stage">
        <Photo row={row} absent={photoAbsent} onAbsent={onPhotoAbsent} />
        <p className="review-next" title={next === null ? undefined : `${text(next.entry.read.name) ?? 'not identified'} ${priceText(next.entry.market)} ${reasonLabel(next.entry.reason)}`}>
          {next === null ? (
            <span className="review-next-empty">Last in the queue</span>
          ) : (
            <>
              <span className="review-next-label">Next</span>
              <span className="review-next-name">{text(next.entry.read.name) ?? 'not identified'}</span>
              {/* A dollar figure is the kit's `Money` (D221, mono); "no market price" is words. */}
              {priceOf(next.entry.market) === null ? (
                <span className="review-next-price">{priceText(next.entry.market)}</span>
              ) : (
                <Money className="review-next-price" value={priceOf(next.entry.market)} />
              )}
            </>
          )}
        </p>
      </div>

      <div className="review-verdict review-choice" key={row.key}>
        <div className="review-question">
          <h2 className="review-question-title" data-retired={retired ? 'true' : undefined}>
            {retired ? <Icon name="history" size={20} className="review-question-mark" /> : null}
            {questionFor(entry.reason)}
          </h2>
          <p className="review-question-sub">
            {reasonLabel(entry.reason)}
            {row.shadow === undefined ? null : <Pill tone="warn">also {row.shadow}</Pill>}
          </p>
        </div>

        <Claims entry={entry} claims={claims} />

        <p className="review-sentence" data-retired={retired ? 'true' : undefined}>
          {parts.map((part, at) => {
            if (part.kind === 'text') return <span key={at}>{part.text}</span>
            if (part.kind === 'claim') {
              return (
                <span key={at} className="review-claim" title={part.raw === part.text ? undefined : part.raw}>
                  {part.text}
                </span>
              )
            }
            if (part.kind === 'name') return <span key={at}>{part.text}</span>
            return (
              <span key={at} className="review-value">
                {part.text}
              </span>
            )
          })}
        </p>

        {showCatalog ? (
          <CatalogPanel lookup={lookup} failed={lookupFailed} typed={typed} onTyped={onTyped} onSearch={onSearch} onChoose={onChooseCatalog} overruling={looking} busy={busy} />
        ) : (
          <>
            {head === null ? null : (
              <div className="review-shared">
                <span className="review-shared-name">{head.name}</span>
                <span className="review-shared-meta">
                  <span>{head.set}</span>
                  <span>{head.number}</span>
                </span>
              </div>
            )}
            <ul className="review-candidates">
              {entry.candidates.map((candidate, at) => (
                <li key={`${candidate.sku}:${at}`} style={{ animationDelay: `${at * 40}ms` }}>
                  <CandidateButton candidate={candidate} at={at} shared={head !== null} tags={tagsFor(entry, claims, candidate)} onChoose={() => onChoose(candidate)} disabled={busy} />
                </li>
              ))}
            </ul>
          </>
        )}

        <div className="review-actions">
          <Button variant="quiet" icon="chevronRight" kbd={SKIP_KEY_LABEL} className="review-action" onClick={onSkip} disabled={busy}>
            Skip
          </Button>
          {entry.candidates.length === 0 ? null : (
            <Button
              variant="quiet"
              icon={looking ? 'undo' : 'search'}
              kbd={looking ? 'Esc' : LOOKUP_KEY_LABEL}
              className="review-action"
              onClick={onLookup}
              disabled={busy}
              aria-expanded={looking}
            >
              {looking ? 'Back to listings' : phone ? 'Search TCGplayer' : 'Search TCGplayer\'s list'}
            </Button>
          )}
          {/* ICON-MAP (review): words at every width, including the phone — dropped
              `iconOnly` on purpose. `words="not-in-vocabulary"`: this "Close" means "close
              this question without answering it" (D37's stand-down umbrella), not the
              vocabulary's generic dismiss-a-panel sense the rule is written for. */}
          <Button
            variant="quiet"
            icon="x"
            kbd={phone ? undefined : CLOSE_KEY_LABEL}
            className="review-action review-action-close"
            onClick={onClose}
            disabled={busy}
            aria-expanded={closing}
            words="not-in-vocabulary"
          >
            Close
          </Button>
          {activity === null ? null : <Busy activity={activity} />}

          {!closing ? null : (
            <>
              <div className="bn-scrim review-close-scrim" onClick={onClose} aria-hidden="true" />
              <ClosePanel onChoice={onCloseChoice} onClose={onClose} disabled={busy} />
            </>
          )}
        </div>

        {tray}

        <Facts row={row} />
      </div>
    </section>
  )
}

/* The evidence, as chips: what the stack was sorted as (Capture's Finish field) and what
 * the photograph read, in the two tints the row tags reuse. Only reasons with a claim to
 * show draw any. */
function Claims({ entry, claims }: { entry: QueueEntryWire; claims: Claims }) {
  const chips: ReactNode[] = []
  if (FINISH_REASONS.has(entry.reason)) {
    if (claims.sorted !== null) {
      chips.push(
        <span key="sorted" className="review-chip review-chip-sorted" title={`Finish at capture: ${claims.sorted.join(' or ')}`}>
          <Icon name="hand" size={12} />
          <span className="review-chip-key">Sorted as</span>
          <span className="review-chip-value">{claims.sorted.map(humanize).join(' or ')}</span>
        </span>,
      )
    }
    if (claims.photo !== null) {
      chips.push(
        <span key="photo" className="review-chip review-chip-photo" title={`The photograph read as ${claims.photo}`}>
          <Icon name="camera" size={12} />
          <span className="review-chip-key">Photo</span>
          <span className="review-chip-value">{humanize(claims.photo)}</span>
        </span>,
      )
    }
  }
  if (entry.reason === 'set_ambiguous' && claims.hint !== null) {
    chips.push(
      <span key="hint" className="review-chip review-chip-sorted" title="The set hint recorded at capture">
        <Icon name="tag" size={12} />
        <span className="review-chip-key">Set hint</span>
        <span className="review-chip-value review-chip-value-mono">{claims.hint}</span>
      </span>,
    )
  }
  if (entry.reason === 'low_confidence') {
    const confidence = text(entry.confidence) ?? 'low'
    chips.push(
      <span key="conf" className="review-chip review-chip-warn" title={`Confidence: ${confidence}`}>
        <Icon name="eye" size={12} />
        <span className="review-chip-key">Confidence</span>
        <span className="review-chip-value">{humanize(confidence)}</span>
      </span>,
    )
  }
  if (entry.reason === 'rarity_claim_mismatch' || entry.reason === 'name_disputed') {
    chips.push(
      <span key="rarity" className="review-chip review-chip-warn">
        <Icon name="alert" size={12} />
        These rows may be another card
      </span>,
    )
  }
  {
    /* THE CLAIM ITSELF, BESIDE THE FINISH TOGGLE IT HAS ALWAYS SAT NEXT TO IN THE STORE.
     * Drawn for every reason and not only the contradiction: the claim narrowed the rows on
     * every card it was made for (D23 job (a) filters before any rung reads them), so it is
     * context for the whole queue rather than evidence for one entry. */
    const claimed = claimMembers(entry.read.rarity_claim)
    if (claimed !== null) {
      chips.push(
        <span key="claim" className="review-chip" title={`Rarity claimed at capture: ${claimed.join(', ')}`}>
          <Icon name="tag" size={12} />
          {/* "Claimed" alone did not say claimed WHAT — the walkthrough's "CLAIMED · Showcase"
              reads as a verdict rather than a fact about the rarity, unlike "Sorted as" and
              "Photo" beside it, which both name their subject. "Rarity" matches that pattern
              at the SAME word count (D194's ratchet forbids a route's words rising), and the
              `title` above still spells the whole sentence out for a hover. */}
          <span className="review-chip-key">Rarity</span>
          <span className="review-chip-value">
            {claimed.map((one, at) => (
              <span key={at}>{humanize(one)}</span>
            ))}
          </span>
        </span>,
      )
    }
  }
  /* UX-251/D28: always the reserved frame, chips or not, so a card with no evidence chips
   * does not pull the candidate rows below it up into the space a neighbouring card's chips
   * used. The frame's own min-height (ReviewQueue.css) does the actual reserving; an empty
   * `<div>` here is what lets it apply on a card with nothing to show. */
  return <div className="review-claims">{chips}</div>
}

/** Exported for `CardHero.tsx`'s listing-correction control, which reuses this row rather
 *  than forking one (D252, on this file's own header: "if reusing the
 *  pane needs a component lifted out... do that — that is added to inventory... not a
 *  fork"). No behavior here changed to make that reuse possible. */
export function CandidateButton({
  candidate,
  at,
  shared,
  tags,
  onChoose,
  disabled,
  fromCatalog,
}: {
  candidate: CandidateRow
  at: number
  shared: boolean
  tags: Evidence[]
  onChoose: () => void
  disabled: boolean
  fromCatalog?: boolean
}) {
  const unpriced = priceOf(candidate.market) === null
  const keyed = at < MAX_KEYED_CANDIDATES
  return (
    <button
      type="button"
      className="review-candidate"
      onClick={onChoose}
      disabled={disabled}
      title={`SKU ${candidate.sku}`}
      aria-keyshortcuts={keyed ? String(at + 1) : undefined}
      data-from={fromCatalog ? 'catalog' : undefined}
    >
      {keyed ? (
        <Kbd className="review-key bn-kbd-lg">{at + 1}</Kbd>
      ) : (
        <span className="review-key review-key-blank bn-kbd-lg" aria-hidden="true" title="No key. Click this row.">
          –
        </span>
      )}
      <span className="review-candidate-main">
        {shared ? (
          <span className="review-candidate-name review-candidate-condition">
            {/* The card is named once above the rows; it stays in each row's accessible name. */}
            <span className="bn-sr">{candidate.name} </span>
            {candidate.condition}
          </span>
        ) : (
          <>
            <span className="review-candidate-name">{candidate.name}</span>
            <span className="review-candidate-meta">
              <span className="review-candidate-condition">{candidate.condition}</span>
              <span>{candidate.set}</span>
              <span>{candidate.number}</span>
            </span>
          </>
        )}
      </span>
      {tags.length === 0 ? null : (
        <span className="review-candidate-tags">
          {tags.map((tag) => (
            <span key={tag} className={`review-tag review-tag-${tag}`} title={TAG_TITLES[tag]}>
              {TAG_WORDS[tag]}
            </span>
          ))}
        </span>
      )}
      <span className={unpriced ? 'review-candidate-price is-unpriced' : 'review-candidate-price'}>{priceText(candidate.market)}</span>
    </button>
  )
}

/* D37's panel — a dialog on a desktop, a sheet on a phone. Digits 1–7 and Escape are the
 * container's; this draws, takes focus while it is up, keeps Tab inside itself, and hands
 * focus back to the control that raised it when it goes. */
function ClosePanel({ onChoice, onClose, disabled }: { onChoice: (choice: CloseChoice) => void; onClose: () => void; disabled: boolean }) {
  const panel = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    /* Raised by a click, focus goes back to the control that was pressed; raised by `X`
     * with nothing focused, it goes to the Close button, which is the control that names
     * this panel (`aria-expanded`). The host is read now: the ref is detached by the time
     * this cleanup runs. */
    const active = document.activeElement
    const opener = active instanceof HTMLElement && active !== document.body ? active : null
    const host = panel.current?.parentElement ?? null
    panel.current?.focus({ preventScroll: true })
    return () => {
      const target = opener !== null && opener.isConnected ? opener : host?.querySelector<HTMLElement>('.review-action-close')
      target?.focus({ preventScroll: true })
    }
  }, [])

  const trapTab = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Tab' || panel.current === null) return
    const stops = [...panel.current.querySelectorAll<HTMLElement>('button:not(:disabled), [href], input:not(:disabled), [tabindex]:not([tabindex="-1"])')]
    const first = stops[0]
    const last = stops[stops.length - 1]
    if (first === undefined || last === undefined) return
    const active = document.activeElement
    if (event.shiftKey && (active === first || active === panel.current)) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && active === last) {
      event.preventDefault()
      first.focus()
    }
  }

  const group = (kind: CloseChoice['kind'], title: string, note: string) => (
    <div className="review-close-group">
      <div className="review-close-head">
        <span>{title}</span>
        <span className="review-close-note">{note}</span>
      </div>
      {CLOSE_CHOICES.map((option, at) =>
        option.choice.kind !== kind ? null : (
          <button key={option.machine} className="review-close-choice" type="button" onClick={() => onChoice(option.choice)} disabled={disabled}>
            <Kbd className="review-key bn-kbd-lg">{at + 1}</Kbd>
            <span className="review-close-text">
              <span className="review-close-label">{option.label}</span>
              <span className="review-close-why">{option.note}</span>
            </span>
            <span className="review-code">{option.machine}</span>
          </button>
        ),
      )}
    </div>
  )
  return (
    <div className="review-close bn-dialog" role="dialog" aria-modal="true" aria-label="Close this card without answering it" ref={panel} tabIndex={-1} onKeyDown={trapTab}>
      <div className="review-close-title">
        <span className="bn-section-title">Close without answering</span>
        <IconButton icon="x" label="Close the panel" kbd="Esc" size="sm" onClick={onClose} />
      </div>
      <p className="review-close-lede">Stops the queue asking about it. Can be undone.</p>
      {group('stand_down', 'Stand down', 'the card stays where it is')}
      {group('retire', 'Retire', 'the card leaves inventory, its slot stays empty')}
      <p className="review-close-foot">Delete the capture on Inventory — renumbers cards behind it, cannot be undone.</p>
    </div>
  )
}

// --------------------------------------------------------------------------- the catalog

export type CatalogPanelProps = {
  lookup: CatalogLookup | null
  failed: string | null
  typed: string
  onTyped: (text: string) => void
  onSearch: () => void
  onChoose: (row: CandidateRow) => void
  overruling: boolean
  busy: boolean
}

/* D46 — rows out of the export, drawn through the same row and answered on the same digits.
 * The search heads the list; the mode line says whose rows these are.
 *
 * EXPORTED FOR `CardHero.tsx`'s LISTING-CORRECTION CONTROL, this file's own header rule:
 * "added to inventory and both screens get it, not a fork." `overruling` reads oddly for
 * that caller — there is no candidate list to have looked away from — so it always passes
 * `true`, which draws the plain "Rows from the export, matched by name" copy. That caller
 * binds `Escape` on its own panel, so "Esc goes back" is true there too. */
export function CatalogPanel({ lookup, failed, typed, onTyped, onSearch, onChoose, overruling, busy }: CatalogPanelProps): ReactNode {
  const rows = lookup?.rows ?? []
  // NO CUTOFF, THEN A KEYBOARD LIMIT (owner's ruling, 2026-09-24: "the search shouldn't
  // cut off i should see all rows that matched unless it's an egregious amount ... or a
  // 'show 10 more' etc"). The server sends every match up to its own egregious ceiling
  // (`CATALOG_EGREGIOUS_LIMIT`); `revealed` is how many of THOSE rows this press has
  // uncovered, never a second network round trip — D118: a press adds rows below and
  // moves nothing above it. Reset per search, so an earlier reveal never survives a typed
  // query it does not belong to.
  const [revealed, setRevealed] = useState(MAX_KEYED_CANDIDATES)
  useEffect(() => setRevealed(MAX_KEYED_CANDIDATES), [lookup?.query])
  const shown = rows.slice(0, revealed)
  const more = rows.length - shown.length
  return (
    <div className="review-catalog">
      <div className="review-catalog-head">
        <span className="review-catalog-mode">
          <Icon name="search" size={14} />
          {overruling ? (
            <>
              Rows from the export, matched by name. <Kbd>Esc</Kbd> goes back.
            </>
          ) : (
            <>No matching row. These are export rows matched on what was read.</>
          )}
        </span>
        <form
          className="review-catalog-search"
          onSubmit={(event) => {
            event.preventDefault()
            onSearch()
          }}
        >
          <label className="bn-sr" htmlFor="review-catalog-q">
            Search this export
          </label>
          <span className="bn-input-wrap review-catalog-wrap">
            <Icon name="search" size={16} />
            <input
              id="review-catalog-q"
              className="bn-input review-catalog-input"
              type="search"
              value={typed}
              placeholder="Name, collector number, or SKU"
              onChange={(event) => onTyped(event.target.value)}
              disabled={busy}
            />
          </span>
          <Button type="submit" disabled={busy}>
            Search
          </Button>
        </form>
      </div>

      {failed !== null ? (
        <Notice tone="danger">{failed}</Notice>
      ) : lookup === null ? (
        <div className="review-candidates" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <div key={i} className="bn-skeleton review-candidate-skeleton" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <p className="review-catalog-empty">
          Nothing in that export matches {lookup.query ? `“${lookup.query}”` : 'this card'}. Search by name, collector number or SKU, or close the card.
        </p>
      ) : (
        <ul className="review-candidates">
          {shown.map((row, at) => (
            <li key={`${row.sku}:${at}`} style={{ animationDelay: `${at * 40}ms` }}>
              <CandidateButton candidate={row} at={at} shared={false} tags={[]} onChoose={() => onChoose(row)} disabled={busy} fromCatalog />
            </li>
          ))}
        </ul>
      )}

      {more > 0 ? (
        <Button variant="ghost" block onClick={() => setRevealed((n) => n + CATALOG_REVEAL_STEP)} disabled={busy}>
          Show {Math.min(more, CATALOG_REVEAL_STEP)} more
        </Button>
      ) : null}

      {lookup !== null && lookup.truncated ? (
        <p className="review-catalog-more">
          Only the first {rows.length} of {lookup.found} rows are shown. Narrow the search to see the rest.
        </p>
      ) : null}
    </div>
  )
}

// ------------------------------------------------------------------------------ the facts

function Facts({ row }: { row: Row }) {
  const { entry } = row
  const facts: { label: string; value: ReactNode; mono?: boolean }[] = [
    { label: 'Card', value: text(entry.read.name) ?? 'not identified' },
    { label: 'Number', value: collectorNumber(entry.read) ?? 'none', mono: true },
    { label: 'Market', value: priceText(entry.market), mono: true },
    { label: 'Confidence', value: humanize(text(entry.confidence) ?? 'none recorded') },
    { label: 'Set hint', value: text(entry.read.set_hint) ?? 'none', mono: true },
    {
      label: 'Sorted as',
      value: (() => {
        const members = claimMembers(entry.read.metadata_finish)
        if (members === null) return 'no claim'
        return (
          <span className="review-fact-multi">
            {members.map((member, at) => (
              <span key={at}>{member}</span>
            ))}
          </span>
        )
      })(),
      mono: true,
    },
    { label: 'Photo read', value: text(entry.read.detected_finish) ?? 'none', mono: true },
    {
      label: 'Queue',
      value:
        row.shadow === undefined ? (
          humanize(row.queue)
        ) : (
          <span className="review-fact-multi">
            <span>{humanize(row.queue)}</span>
            <span>also {humanize(row.shadow)}</span>
          </span>
        ),
    },
    { label: 'Waiting', value: seenText(entry) },
    // No `Position` fact: the photo caption already names the card's place, and the place
    // shows once on this screen.
  ]
  return (
    <details className="review-details">
      <summary className="review-details-summary">
        <Icon name="chevronRight" size={14} className="review-details-caret" />
        This read
        <span className="review-details-hint">what the run recorded about this card</span>
      </summary>
      <dl className="review-facts">
        {facts.map((fact) => (
          <div className="review-fact" key={fact.label}>
            <dt>{fact.label}</dt>
            <dd className={fact.mono ? 'bn-mono' : undefined}>{fact.value}</dd>
          </div>
        ))}
      </dl>
    </details>
  )
}

// ------------------------------------------------------------------------------ the photo

/* D4: the stored capture beside the rows; the card never leaves its box. Four states in one
 * reserved frame (D28) so the rows never move: loaded, loading, failed, never existed. */
function Photo(props: { row: Row; absent: boolean; onAbsent: () => void }) {
  return (
    <div className="review-frame review-well">
      <PhotoContent {...props} />
    </div>
  )
}

function PhotoContent({ row, absent, onAbsent }: { row: Row; absent: boolean; onAbsent: () => void }) {
  const { entry } = row
  const [aim, setAim] = useState<LoupeAim | null>(null)

  if (entry.box < 1) {
    return (
      <AbsentPhoto
        title="No position, so no photograph"
        detail={
          <span className="review-fact-multi">
            <span>box {entry.box}</span>
            <span>index {entry.index}</span>
          </span>
        }
        label={entry.label}
      >
        This entry reached the queue before it was given a place in a box.
      </AbsentPhoto>
    )
  }

  if (entry.photo === null) {
    return (
      <AbsentPhoto title="No photograph was stored" detail="photo: null" label={entry.label} box={entry.box} cid={entry.cid} place={entry.place}>
        The record carries no photograph at all.
      </AbsentPhoto>
    )
  }

  /* THE SLOT ROUTE, BECAUSE A QUEUE ENTRY HAS NO NAME TO ADDRESS BY (D172). `_queue_row` is
     `asdict(QueueEntry)`, and that record — written by `cli/resolve.py` at join time and read
     back out of the store's queue table — carries `box`, `index`, `label` and `photo` and no
     `cid`: the queues predate the name by a long way, and nothing re-derives one for an entry
     that is already waiting. `GET /photo/<box>/<index>` is the correct address for it and is
     kept for exactly this population, alongside the 3,629 position records in 12 immutable
     `runs/<n>/pricing.json` files. Its `no-cache` and its digest ETag are what keep this
     picture honest while the box shifts under it. */
  const src = photoUrl(entry.box, entry.index)

  if (absent) {
    return (
      <AbsentPhoto title="The file is not on disk" detail={src} label={entry.label} box={entry.box} cid={entry.cid} place={entry.place}>
        The entry has a photograph and nothing here can restore it. The card is still at its slot.
      </AbsentPhoto>
    )
  }

  return (
    <>
      <img
        key={row.key}
        className="review-photo"
        src={src}
        alt={`The card photographed at ${entry.label}`}
        onError={onAbsent}
        draggable={false}
        onPointerMove={(event) => setAim(loupeAim(event.currentTarget, event.clientX, event.clientY))}
        onPointerLeave={() => setAim(null)}
      />
      {aim === null ? null : (
        <span
          className="review-inset"
          style={{
            backgroundImage: `url(${src})`,
            backgroundPosition: `${-aim.bx}px ${-aim.by}px`,
            left: `${aim.x + aim.ox - LOUPE / 2}px`,
            top: `${aim.y + aim.oy - LOUPE / 2}px`,
          }}
          aria-hidden="true"
        />
      )}
      <PositionCaption label={entry.label} box={entry.box} cid={entry.cid} place={entry.place} />
      <span className="review-stage-hint" aria-hidden="true">
        <Icon name="scan" size={12} />
        1:1 under the pointer
      </span>
    </>
  )
}

function AbsentPhoto({ title, detail, label, box, cid, place, children }: { title: string; detail: ReactNode; label: string; box?: number; cid?: string | null; place?: Place; children: ReactNode }) {
  return (
    <div className="review-absent">
      <span className="review-absent-art">
        <Icon name="image" size={22} />
      </span>
      <p className="review-absent-title">{title}</p>
      <p className="review-absent-body">{children}</p>
      <p className="review-code review-absent-detail">{detail}</p>
      <PositionCaption label={label} box={box} cid={cid} place={place} />
    </div>
  )
}

/* The card's address, and the way back to it: this opens THE CARD on Inventory
 * (`#/inventory?box=<n>&card=<cid>`), not the box at its first card (LOC-12). The label names
 * the box by its name (D259), and its accessible name is the place as a
 * sentence (`Box 1, Section 3, Card 13`). A card with no box has no destination and draws the
 * plain caption; a card the server sent no name for opens its box.
 *
 * THE PILL SHOWS WHICH END IS THE BACK, AND ITS NEIGHBOURS (UX-228, LOC-26). The owner's ruling:
 * every position drawing shows the orientation, card 1 at the far back. Two thirty-character
 * names and a label do not fit a pill over the photograph, so the neighbours ride one compact
 * line under the label: `back`, the card toward the back, this card, the card toward the front,
 * `front`, with arrows drawn by the kit and never typed (D218). A screen reader hears the
 * same sentence the Fulfiller reads (`placeParts`), not the arrows. */
function CaptionOrder({ place }: { place?: Place }) {
  if (place === undefined || place.located === false) return null
  const parts = placeParts(place, isDeparted(place))
  const side = (which: 'back' | 'front') => {
    const neighbor = parts === null ? null : which === 'back' ? parts.prev : parts.next
    if (neighbor === null) return null
    return (
      <span className={`review-caption-nb${neighbor.name === null ? ' is-unread' : ''}`} data-side={which}>
        {neighborWords(neighbor)}
      </span>
    )
  }
  const back = side('back')
  const front = side('front')
  return (
    <>
      <span className="review-caption-order" aria-hidden="true">
        <span className="review-caption-end">back</span>
        {back}
        {back === null ? null : <Icon name="arrowRight" size={12} className="review-caption-arrow" />}
        <span className="review-caption-this">this card</span>
        {front === null ? null : <Icon name="arrowRight" size={12} className="review-caption-arrow" />}
        {front}
        <span className="review-caption-end">front</span>
      </span>
      {parts === null ? null : <span className="bn-sr">{parts.said}</span>}
    </>
  )
}

function PositionCaption({ label, box, cid, place }: { label: string; box?: number; cid?: string | null; place?: Place }) {
  const inner = (
    <>
      <Icon name="pin" size={14} />
      <span className="review-caption-body">
        <PositionLabel label={label} flow="run" />
        <CaptionOrder place={place} />
      </span>
    </>
  )
  if (box === undefined || box < 1) return <span className="review-caption review-position">{inner}</span>
  const card = cid === undefined || cid === null || cid === '' ? '' : `&card=${encodeURIComponent(cid)}`
  return (
    <a
      className="review-caption review-position review-caption-link"
      href={`#/inventory?box=${box}${card}`}
      title={card === '' ? 'Open this box on Inventory' : 'Open this card on Inventory'}
    >
      {inner}
      <Icon name="arrowRight" size={14} className="review-caption-go" />
    </a>
  )
}

/* The 1:1 loupe (owner, 2026-08-24): hidden at rest, aimed by the pointer, painting the
 * stored frame at natural size. The <img> box IS the drawn image — no object-fit — so the
 * pointer maps to a natural pixel with no letterbox arithmetic. */
const LOUPE = 220

/* `x`/`y` are the pointer inside the <img>; `ox`/`oy` are the image's offset inside the well
   it is centred in, so the glass is positioned in the well's frame and stays centred on the
   pointer. */
type LoupeAim = { x: number; y: number; ox: number; oy: number; bx: number; by: number }

function loupeAim(img: HTMLImageElement, clientX: number, clientY: number): LoupeAim | null {
  const box = img.getBoundingClientRect()
  const x = clientX - box.left
  const y = clientY - box.top
  if (x < 0 || y < 0 || x > box.width || y > box.height) return null
  if (img.naturalWidth === 0 || img.naturalHeight === 0 || box.width === 0) return null
  const nx = (x / box.width) * img.naturalWidth
  const ny = (y / box.height) * img.naturalHeight
  return { x, y, ox: img.offsetLeft, oy: img.offsetTop, bx: nx - LOUPE / 2, by: ny - LOUPE / 2 }
}

// ------------------------------------------------------------------------- what is waiting

/* The worklist, in the server's order: priced first and descending, unpriced last, parked
 * below. Display only — the way past a card is to answer it or skip it. */
function Waiting({
  rows,
  currentKey,
  deferred,
  filter,
  tally,
  receipts,
  onUndo,
  onClose,
  disabled,
}: {
  rows: Row[]
  currentKey: string | null
  deferred: readonly string[]
  filter: string | null
  tally: Tally
  receipts: readonly Receipt[]
  onUndo: (receipt: Receipt) => void
  onClose: () => void
  disabled: boolean
}) {
  const listRef = useRef<HTMLUListElement | null>(null)
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>('[aria-current="true"]')
    el?.scrollIntoView({ block: 'nearest' })
  }, [currentKey])

  const done = tally.answered + tally.closed
  let parkedRuled = false

  return (
    <aside className="review-rail" aria-label="The queue">
      <div className="review-rail-head">
        <span className="bn-section-title">
          <Icon name="list" size={16} />
          Up next
          <Pill>{rows.length}</Pill>
        </span>
        <IconButton icon="x" label="Close the queue" size="sm" onClick={onClose} className="review-rail-close" />
      </div>

      {done === 0 && tally.skipped === 0 && receipts.length === 0 ? null : (
        <div className="review-session">
          <div className="review-session-head">
            <span className="bn-label">This session</span>
            <span className="review-session-tally bn-tnum">
              <span>{tally.answered} answered</span>
              {tally.closed > 0 ? <span>{tally.closed} closed</span> : null}
              {tally.skipped > 0 ? <span>{tally.skipped} skipped</span> : null}
            </span>
          </div>
          <SessionList receipts={receipts} onUndo={onUndo} disabled={disabled} limit={3} />
        </div>
      )}

      <ul className="review-waiting-list" ref={listRef}>
        {rows.map((row) => {
          const rule = row.queue === 'parked' && !parkedRuled
          if (rule) parkedRuled = true
          const skipped = deferred.includes(row.key)
          const age = ageText(row.entry)
          return (
            <li
              key={row.key}
              className="review-row"
              data-band={bandOf(row.entry.market)}
              data-parked={row.queue === 'parked' ? 'true' : undefined}
              data-filtered-out={filter !== null && row.entry.reason !== filter ? 'true' : undefined}
              data-rule={rule ? 'parked' : undefined}
              aria-current={row.key === currentKey ? 'true' : undefined}
            >
              {rule ? (
                <span className="review-row-parked-label">
                  <span>Parked</span>
                  <span>under the threshold</span>
                </span>
              ) : null}
              <span className="review-row-main">
                <span className="review-row-name" title={text(row.entry.read.name) ?? undefined}>
                  {text(row.entry.read.name) ?? 'not identified'}
                </span>
                {priceOf(row.entry.market) === null ? (
                  <span className="review-row-price">{priceText(row.entry.market)}</span>
                ) : (
                  <Money className="review-row-price" value={priceOf(row.entry.market)} />
                )}
              </span>
              <span className="review-row-sub">
                <span className="review-row-position">
                  <PositionLabel label={row.entry.label} flow="run" />
                </span>
                <span className="review-row-reason" title={row.entry.reason}>
                  {reasonLabel(row.entry.reason)}
                </span>
                {/* No `parked` pill: every row under the rule below is parked, and the rule
                    says so once rather than on each of them. */}
                {row.shadow === undefined ? null : <span className="review-row-pill">also {row.shadow}</span>}
                {skipped ? <span className="review-row-pill">skipped</span> : null}
                {age === null ? null : <span className="review-row-pill">{age}</span>}
              </span>
            </li>
          )
        })}
      </ul>
    </aside>
  )
}

// ------------------------------------------------------- the store-wide re-check (a sheet)

/* EVERY WAITING CARD, PUT BACK THROUGH THE LADDER — `POST /queues/refresh`, reachable from
 * this screen's header because this is the screen the waiting cards are on.
 *
 * TWO PRESSES, PREVIEW FIRST, AND THE SECOND CONTROL DOES NOT EXIST UNTIL THE FIRST HAS
 * ANSWERED. `LiveReconcile`'s shape (D87) and for its reason: this rewrites every open entry
 * in the store in one act, so what it would do is READ before it is done. The preview runs on
 * opening — there is nothing to ask for first, no file, no scope, no figure — and writes
 * nothing. `Apply the refresh` is rendered only once a preview has landed, absent rather than
 * disabled: a control that cannot be pressed yet still says the press is available.
 *
 * IT IS NOT THE `R` RELOAD. That re-fetches these two queues and asks the pipeline nothing.
 * This re-resolves each open entry against the export its run was joined against, which is
 * what a frozen entry needs — so a write can clear a card outright, and the queue list is
 * RE-READ afterwards through the screen's own `reload` rather than patched from here.
 *
 * AN ANSWERED CARD IS NEVER RE-QUEUED, AND THE SHEET SAYS SO. `store/queues.py:upsert`
 * refuses a cleared position and `release` refuses to drop one, so D28's undo stays the only
 * door back out of an answer. It is on screen because the operator is being asked for a
 * store-wide write over the work they have just been doing by hand.
 *
 * A NON-ZERO EXIT IS AN ANSWER, NOT A CRASH. The command's own stdout is the only thing that
 * says what went wrong, so a refusal draws the console too, under a danger notice carrying
 * the exit code. What CANNOT be drawn is a request that never reached the command — that is a
 * `Failure`, and it gets the message and the code it came with. */
function QueueRefresh({
  open,
  onClose,
  onWrote,
}: {
  readonly open: boolean
  readonly onClose: () => void
  /** The screen's own queue re-read, pressed once a write has landed. */
  readonly onWrote: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [report, setReport] = useState<string | null>(null)
  const [wrote, setWrote] = useState(false)
  /** The command's own exit code when it refused; null while it has not. */
  const [refused, setRefused] = useState<number | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const sheet = useRef<HTMLElement | null>(null)
  const scrim = useRef<HTMLDivElement | null>(null)

  const send = useCallback(
    async (write: boolean) => {
      setBusy(true)
      setFailure(null)
      try {
        const answer = await refreshQueues({ write })
        setReport(answer.console)
        setWrote(answer.ok && answer.wrote)
        setRefused(answer.ok ? null : answer.exit_code)
        if (answer.ok && answer.wrote) {
          toast({
            kind: 'ok',
            title: 'The queues were re-checked',
            body: 'Every card that could be answered has left the queue.',
          })
          onWrote()
        }
      } catch (err) {
        setFailure(describeFailure(err))
      } finally {
        setBusy(false)
      }
    },
    [onWrote],
  )

  /* The preview, on opening, once. Reopening takes a FRESH reading rather than showing the
     last one — answers have usually been written in between, and a preview describing the
     queue as it was two minutes ago is the one thing a two-step gate may not show. The ref is
     what keeps StrictMode's second mount from sending it twice. */
  const asked = useRef(false)
  useEffect(() => {
    if (!open) {
      asked.current = false
      return
    }
    if (asked.current) return
    asked.current = true
    setReport(null)
    setWrote(false)
    setRefused(null)
    setFailure(null)
    void send(false)
  }, [open, send])

  /* Focus lands inside on open, stays inside under Tab, and returns to the header button on
     close; Escape closes unless a read or a write is in flight. */
  useOverlayFocus(sheet, open, onClose, busy, scrim)

  /* The press that writes exists only while there is a preview to have read and nothing has
     been written yet. A refusal takes it away too: the write would refuse identically, and
     the remedy is in the console rather than in a second press. */
  const applyable = report !== null && !wrote && refused === null

  /* Portalled to <body>: `main.bn-page` keeps a filled transform after its enter animation,
     and a fixed sheet inside it would hang off the column. */
  return createPortal(
    <>
      {open ? <div ref={scrim} className="bn-scrim" onClick={onClose} /> : null}
      <aside
        ref={sheet}
        className="bn-sheet review-recheck"
        hidden={!open}
        role="dialog"
        aria-modal="true"
        aria-labelledby="review-recheck-head"
        tabIndex={-1}
      >
        <header className="review-recheck-top">
          <div className="review-recheck-heading">
            <span className="bn-eyebrow review-fact-multi">
              <span>Store-wide</span>
              <span>free</span>
            </span>
            <h2 className="review-recheck-head" id="review-recheck-head">
              Re-check every waiting card
            </h2>
          </div>
          <IconButton icon="x" label="Close" onClick={onClose} />
        </header>

        <div className="review-recheck-body">
          <p className="review-recheck-says">
            Re-resolves every waiting card against the current export. A card it can place
            leaves the queue; the rest stay, often with a better reason.{' '}
            <strong>Nothing is uploaded and nothing is identified</strong> — free, and safe to
            run again.
          </p>

          {/* WHAT IT WILL NOT DO, said before the press rather than in the receipt. The
              operator has just spent the session answering cards by hand, and a store-wide
              write over that work has to state what it cannot reach. */}
          <p className="review-recheck-safe">
            <Icon name="lock" size={14} />
            <span>
              An already-answered card never returns to the queue. Only <strong>Undo</strong>{' '}
              reverses an answer.
            </span>
          </p>

          {!busy ? null : (
            <p className="review-recheck-status" role="status">
              <span className="bn-dot bn-dot-accent" />
              {report === null ? 'Reading what would change…' : 'Re-checking every waiting card…'}
            </p>
          )}

          {/* THE SHAPE OF THE ANSWER WHILE IT IS COMING, in the idiom this screen already uses
              for the catalog rows. Only on the FIRST read: once there is a report, replacing it
              with bars would take away the thing the operator is deciding from, and the status
              line above already says a write is in flight. The bars are decoration for a
              sentence that is `role="status"`, so they are hidden from the reader. */}
          {busy && report === null ? (
            <div className="review-recheck-wait" aria-hidden="true">
              {[0, 1, 2].map((at) => (
                <span key={at} className="bn-skeleton review-recheck-wait-line" />
              ))}
            </div>
          ) : null}

          {failure === null ? null : (
            /* The TITLE carries the reassurance, not the body. `describeFailure`'s own
               messages already end with one — `origin_blocked`'s says "Nothing was saved" —
               and appending a second read as two different claims about one refusal. */
            <Notice tone="danger" title="The re-check did not run, and nothing was written" code={failure.code}>
              {failure.message}
            </Notice>
          )}

          {report === null ? null : (
            <>
              {refused !== null ? (
                <Notice tone="danger" title="The re-check refused" code={`exit ${refused}`}>
                  Stopped on its own. Output is below.
                </Notice>
              ) : wrote ? (
                <Notice tone="ok" title="Re-checked">
                  Queues written and re-read. Your answers are untouched.
                </Notice>
              ) : (
                <Notice tone="info" title="Preview — nothing written yet">
                  Read what would move, then apply it below.
                </Notice>
              )}
              <LogWell
                text={report}
                label={wrote ? 'What the re-check printed' : 'What the preview printed'}
                className="review-recheck-console"
                maxHeight={360}
              />
            </>
          )}
        </div>

        {!applyable ? null : (
          <footer className="review-recheck-foot">
            <Button variant="ghost" onClick={onClose} disabled={busy}>
              Not now
            </Button>
            <Button variant="primary" icon="check" busy={busy} disabled={busy} onClick={() => void send(true)}>
              Apply the refresh
            </Button>
          </footer>
        )}
      </aside>
    </>,
    document.body,
  )
}
