import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CandidateRow, QueueEntryWire, QueueName, QueueRead, QueueSnapshot } from './types'
import type { Failure } from './server'
import { ServerError, answerReview, describeFailure, getQueues, photoUrl } from './server'
import './ReviewQueue.css'

/* The review queue — build-order step 7b, specified in docs/DESIGN.md's own section.
 *
 * "The hardest screen in the product and the one the owner spends hours in, so its shape is
 * part of the design and not left to step 7." Every structural choice below is that
 * section's, not this file's: one card at a time, photo first, single column; the sentence
 * before the candidates; the price-driven type scale; accent outlined and never filled where
 * there are two answers; the human label above the machine string; a key on every choice.
 *
 * BUILT BEFORE GATE B, WHICH ITS OWN SPEC SAYS NOT TO DO. docs/specs/capture-app.md §0 puts
 * 7b after the gate so it is designed against a real run; the owner overruled that on this
 * branch. The consequence is not decorative and is worth stating where the code is rather
 * than only in the spec: THE DATA THIS SCREEN DISPLAYS HAS NEVER EXISTED. No card has been
 * photographed, no `identify` run has been paid for, and `review.json` has never held a row.
 * Everything here is built to the document; nothing here has been held against a queue.
 *
 * So every number this file invents — the price bands, and only the price bands — is marked
 * as an assumption at the place it is invented, with what would settle it. Nothing else is
 * invented: the reason strings, the entry shape, the candidate shape, the sort and the
 * two-queue split are all read out of the modules that produce them, and the answer's shape
 * is read out of the route that takes it.
 *
 * TWO ROUTES, BOTH BUILT THIS SESSION IN `server/capture_server.py`:
 *
 *   GET  /queues                      both standing queues, already in worked order
 *   POST /review/<box>/<index>/answer one candidate row, chosen  (D4)
 *
 * The second one settled a question this screen had guessed at and guessed wrong. An earlier
 * draft offered "Leave unlisted" as a way to clear a card without picking a row; the route
 * has no such path, refuses an entry with no candidates outright, and requires `condition`
 * alongside `sku` so that a stale screen is caught rather than obeyed. Both are recorded at
 * the code they changed rather than only here.
 *
 * WHAT IS NOT HERE, and deliberately: no confirm dialog, no success acknowledgement to
 * dismiss, no list -> detail -> back loop. docs/DESIGN.md forbids all three by name.
 * Answering writes the answer and advances.
 */

/* ----------------------------------------------------------------------------- the wire
 *
 * THE SHAPES AND THE TWO CALLS LIVE IN types.ts AND server.ts, and did not always. They were
 * written here, in the session that built this screen, because those two files belonged to
 * another group that day and importing two names that do not exist is a build nobody can then
 * look at. They moved out on 2026-08-13 when the screens were wired, which is what the note
 * they carried asked for: one module owns every call to the capture server, because the
 * failure behaviour is one decision and a decision spread across four components is four
 * decisions that drift.
 *
 * What is left here is what this screen does with them — the reason labels, the price bands,
 * the sentence, the worklist. None of it is a second opinion about the wire.
 */

// --------------------------------------------------------------------------- reason codes

/* The twelve, transcribed from the two modules that emit them: six from
 * `pipeline/variant.py` (the D3 ladder's review reasons) and six from `pipeline/routing.py`
 * (v2 §5.4's routing reasons). docs/DESIGN.md requires each on screen as a human label with
 * the machine string small beneath it, because a friendly label alone is a second vocabulary
 * that nothing audits and a raw string alone is honest and unreadable.
 *
 * NOTHING KEEPS THIS MAP IN STEP WITH THOSE MODULES, and pretending otherwise would be
 * worse than saying so. A TypeScript file cannot import a Python constant, and no check in
 * this repo compares the two — the same gap `docs/DEBTS.md` records for `tokens.css` against
 * docs/DESIGN.md. What this file does instead is make drift VISIBLE rather than silent: an
 * unknown code renders as itself in both slots, with a sentence saying the screen has no
 * label for it, so a reason added to the pipeline shows up here as a plain string rather
 * than as a blank line.
 *
 * The labels are also the least tested copy in the product, and for a reason no amount of
 * care fixes: none of these codes has ever fired against a photograph of a card. A label
 * written for a code that fires weekly and one written for a code that fires once a year are
 * different pieces of copy, and there is no way to tell which is which until Gate B runs.
 */
const REASON_LABELS: Readonly<Record<string, string>> = {
  // pipeline/variant.py — the ladder could not settle the finish.
  no_catalog_row: 'Not in the export',
  metadata_not_stocked: 'Toggle names a finish that is not stocked',
  metadata_detection_disagreement: 'Toggle and photo disagree',
  detected_finish_not_stocked: 'Photo names a finish that is not stocked',
  ambiguous_no_signal: 'Nothing decided the finish',
  duplicate_condition: 'Two rows, one condition',

  // pipeline/routing.py — the answer exists but is not trusted enough to list.
  low_confidence: 'Low confidence read',
  no_position: 'No position recorded',
  identification_failed: 'Identification failed',
  set_ambiguous: 'Two sets share this number',
  card_not_detected: 'No card found in the photograph',
  /* Reachable on screen only if the route puts it in a queue. `cli/resolve.py:entries_for`
   * queues `routing.MAIN` and `routing.PARKED`, and `no_market_data` is neither — it is its
   * own destination, priced by hand in decisions.json. Kept because docs/DESIGN.md names
   * twelve, and a map that quietly held eleven would be the drift this comment is about. */
  no_market_data: 'No market price',
}

function reasonLabel(reason: string): string {
  return REASON_LABELS[reason] ?? reason
}

// ------------------------------------------------------------------------- the sentence

/* "Then one sentence naming what the system found." Built as segments rather than a string
 * because docs/DESIGN.md's accent rule reaches inside it: outline and text weight mark the
 * two conflicting claims, which is the common case on this screen, and a sentence assembled
 * by template could not mark them.
 *
 * Three kinds, and the split is the design's rather than convenience:
 *
 *   text   a sentence a human reads          body face
 *   value  a pipeline value, uncontested     utility face, ink
 *   claim  one of two claims in conflict     utility face, accent
 *
 * `value` exists because "mono carries all metadata" applies inside a sentence too — a
 * collector number set in the body face is a collector number that has stopped being
 * greppable. `claim` is `value` plus the accent, and is used ONLY where two claims actually
 * conflict: a reason with one finding gets no accent at all, because a colour that marks
 * every noun marks nothing.
 */
type Segment =
  | { kind: 'text'; text: string }
  | { kind: 'value'; text: string }
  | { kind: 'claim'; text: string }

const say = (text: string): Segment => ({ kind: 'text', text })
const value = (text: string): Segment => ({ kind: 'value', text })
const claim = (text: string): Segment => ({ kind: 'claim', text })

/** A trimmed field, or null. `read` comes off a JSON document that has never existed, so
 *  every field is treated as absent-or-blank rather than trusted to be a string. */
function text(field: string | null | undefined): string | null {
  if (typeof field !== 'string') return null
  const trimmed = field.trim()
  return trimmed === '' ? null : trimmed
}

/* The collector number as the model returned it, unpadded, exactly as PullPreview.tsx shows
 * it and for the same reason: `pipeline/join.py:join_key` zero-fills to three digits to
 * match the export's `Number` column, and doing that here would put a string on screen that
 * nothing in the run ever said. */
function collectorNumber(read: QueueRead): string | null {
  const number = text(read.number)
  if (number === null) return null
  const total = text(read.printed_total)
  return total === null ? number : `${number}/${total}`
}

/** The one condition string the candidates offer, or null when they offer none or several.
 *  Used to name the other side of a contradiction — "you sorted this as normal, and the
 *  export stocks only Near Mint Holofoil" — and deliberately silent when there is more than
 *  one, because the candidate rows below already say it better than a sentence can. */
function soleCondition(candidates: CandidateRow[]): string | null {
  const conditions = new Set(candidates.map((row) => row.condition))
  if (conditions.size !== 1) return null
  const [only] = [...conditions]
  return text(only)
}

/** The condition two candidate rows both claim — `pipeline/variant.py`'s DUPLICATE_CONDITION,
 *  from the other side. Null when the entry does not actually carry the duplicate, which is
 *  possible: the pipeline reviews on the duplicate it saw, and this list is what was stored. */
function duplicatedCondition(candidates: CandidateRow[]): string | null {
  const seen = new Set<string>()
  for (const row of candidates) {
    if (seen.has(row.condition)) return text(row.condition)
    seen.add(row.condition)
  }
  return null
}

/* One sentence per reason. Twelve of them, and they are the part of this file most likely to
 * read wrong once real cards arrive — see the note over REASON_LABELS.
 *
 * Every finish and condition is printed in the pipeline's own spelling: `reverse_holo`, not
 * "reverse holo". docs/DESIGN.md's whole argument for showing the machine string is that
 * what you saw on screen can be found in the run report and in review.json, and a screen
 * that prettifies the values while quoting the codes keeps half of that promise.
 */
function sentence(entry: QueueEntryWire): Segment[] {
  const number = collectorNumber(entry.read)
  const toggle = text(entry.read.metadata_finish)
  const detected = text(entry.read.detected_finish)
  const hint = text(entry.read.set_hint)
  const name = text(entry.read.name)
  const only = soleCondition(entry.candidates)

  switch (entry.reason) {
    case 'no_catalog_row':
      return number === null
        ? [say('The export has no row for this card.')]
        : [say('The export has no row for '), value(number), say('.')]

    case 'metadata_not_stocked': {
      if (toggle === null) return [say('The export stocks no row for the finish recorded on this stack.')]
      const head = [say('You sorted this stack as '), claim(toggle)]
      return only === null
        ? [...head, say(', and the export stocks no such row for this number.')]
        : [...head, say(', and the export stocks only '), claim(only), say(' for this number.')]
    }

    case 'metadata_detection_disagreement':
      return [
        say('You sorted this stack as '),
        claim(toggle ?? 'a finish this entry does not record'),
        say(', and the photograph reads as '),
        claim(detected ?? 'something else'),
        say('.'),
      ]

    case 'detected_finish_not_stocked': {
      const head = [say('The photograph reads as '), claim(detected ?? 'a finish this entry does not record')]
      return only === null
        ? [...head, say(', and the export stocks no such row for this number.')]
        : [...head, say(', and the export stocks only '), claim(only), say(' for this number.')]
    }

    case 'ambiguous_no_signal':
      return [
        say(
          'No finish was recorded for this stack and the photograph did not settle it, so every row below is still possible.',
        ),
      ]

    case 'duplicate_condition': {
      const duplicate = duplicatedCondition(entry.candidates)
      return duplicate === null
        ? [say('Two rows in the export claim the same condition for this number, so nothing can choose between them.')]
        : [
            say('Two rows in the export claim '),
            claim(duplicate),
            say(' for this number, so nothing can choose between them.'),
          ]
    }

    case 'low_confidence': {
      const head: Segment[] =
        name === null
          ? [say('The system read this photograph as a card it could not name')]
          : [say('The system read this photograph as '), value(name)]
      const middle: Segment[] = number === null ? [] : [say(' '), value(number)]
      return [
        ...head,
        ...middle,
        say(', with '),
        claim(text(entry.confidence) ?? 'low'),
        say(' confidence, which is not enough to list it on.'),
      ]
    }

    case 'no_position':
      return [
        say('This card has no box and index recorded, so nothing on this screen can say where it physically is.'),
      ]

    case 'identification_failed':
      return [say('Identification returned nothing at all for this photograph.')]

    case 'set_ambiguous': {
      const head: Segment[] =
        number === null
          ? // The trailing space is the sentence's, not the segment renderer's: `parts.map`
            // draws one span per segment with nothing between them, so a branch that ends
            // flush against the next segment reads as `numbermatches`.
            [say('This collector number ')]
          : [value(number), say(' ')]
      const tail: Segment[] =
        hint === null
          ? [say('and no set hint was recorded to break the tie.')]
          : [say('and the set hint '), claim(hint), say(' names none of them.')]
      return [...head, say('matches rows in more than one set, '), ...tail]
    }

    case 'card_not_detected':
      return [say('No card was found in this photograph, so there was no number corner to crop and read.')]

    case 'no_market_data':
      return [
        say(
          'The row this matched carries no market price, so nothing prices it automatically — a missing price is an unknown price, not a low one.',
        ),
      ]

    default:
      /* A reason this screen has no sentence for. Says so rather than rendering an empty
       * line: the machine string is directly beneath the label, and it is the whole of what
       * the pipeline said. */
      return [
        say('The pipeline sent this card here for a reason this screen has no sentence for. The code beneath the label is the whole of what it said.'),
      ]
  }
}

// -------------------------------------------------------------------------------- money

/* A market price for COMPARISON ONLY, never for display.
 *
 * `market` arrives as the string `Decimal` serialised — `"12.34"`, or `""`, or `"0.00"` —
 * and every price this screen shows is that string verbatim. Nothing is reformatted through
 * a float, so no rounding this file performs can ever reach the screen or an import file.
 * The number below exists to answer one question: which type-size band does this row sit in.
 *
 * Blank and zero both come back null, mirroring `pipeline/pricing.py:has_market_data`: a
 * blank or $0.00 market cell is an UNKNOWN price and not a low one (D9). Collapsing those
 * two into "cheap" is the exact move that sweeps a chase card into the $0.40 bucket.
 */
function priceOf(market: string | null | undefined): number | null {
  if (typeof market !== 'string') return null
  const trimmed = market.trim()
  if (trimmed === '') return null
  const parsed = Number(trimmed)
  if (!Number.isFinite(parsed) || parsed <= 0) return null
  return parsed
}

/** What a price cell says. The string as the pipeline wrote it, with a dollar sign, or the
 *  word for a price that is not there — never `$0.00`, which reads as "worthless" for a card
 *  whose value is simply unknown. */
function priceText(market: string | null | undefined): string {
  const parsed = priceOf(market)
  return parsed === null ? 'no market price' : `$${(market ?? '').trim()}`
}

/* D9's threshold, and the only real number this file has to anchor a type scale to.
 * $0.40 is `pipeline/pricing.py:THRESHOLD` — market at or above it earns a listing, and it
 * is also the cut `pipeline/routing.py` makes between the main queue and parked. */
const THRESHOLD = 0.4

/** Which type-size band a queue row sits in.
 *
 *  ASSUMPTION, and the one docs/specs/capture-app.md's status block calls out by name: the
 *  design requires the row's name size and its price size to both step down as the price
 *  does, and that mapping's input is the spread of `market` values in a real queue file.
 *  No such file has ever existed. The multiples below (25x, 5x, 1x the threshold) are cut as
 *  fractions of a number that is already in the repo, so they follow it if it moves — the
 *  same instinct D9 applies to its sub-threshold bands — but the multiples themselves are a
 *  guess. Settled by the first real run: take the price distribution out of `review.json`
 *  and redraw them, which invalidates nothing in this file except these four numbers.
 *
 *  UNPRICED IS NOT THE BOTTOM BAND, and that is not a rounding of the rule. `pipeline/
 *  routing.py` says it in as many words: no price is not a low price, a misread secret rare
 *  is exactly this case, and an unpriced card sorts last in the main queue but is never
 *  parked. Drawing it smallest would teach the eye the opposite of what routing decided.
 */
type Band = 'top' | 'high' | 'mid' | 'low' | 'unpriced'

function bandOf(market: string | null | undefined): Band {
  const price = priceOf(market)
  if (price === null) return 'unpriced'
  if (price >= THRESHOLD * 25) return 'top'
  if (price >= THRESHOLD * 5) return 'high'
  if (price >= THRESHOLD) return 'mid'
  return 'low'
}

/** How long this card has been waiting, and since when.
 *
 *  THE AGE IS THE SERVER'S ARITHMETIC, NEVER THIS FILE'S. `_queue_row` decorates every entry
 *  with `age_days` precisely so the app does not re-derive it; a date subtraction here would
 *  be a second implementation of `store/queues.py:_age_days`, which is the mistake the
 *  position label already taught this app to refuse. When the field is absent — an older
 *  server, or a `first_seen` the helper would not parse — the date stands alone rather than
 *  being turned into an age locally. */
function seenText(entry: QueueEntryWire): string {
  const since = text(entry.first_seen) ?? 'not recorded'
  const age = entry.age_days
  if (typeof age !== 'number') return since
  return `${age}d · since ${since}`
}

// -------------------------------------------------------------------------------- keys

/* "Every choice shows its key." Owner-side, an hour in this queue is a keyboard and not a
 * mouse, and the visible chip is what the no-confirm-dialog decision looks like in markup.
 *
 * Digits for the candidates, because the choice IS a numbered list and any other mapping
 * would be a second thing to learn. Nine of them: a tenth would need a modifier or a
 * two-key sequence, and a card with ten candidate rows is rare enough that reaching for the
 * mouse is the right cost. Rows past the ninth show no chip rather than a chip that does
 * nothing.
 */
const MAX_KEYED_CANDIDATES = 9

/* The digits are the whole of the answering vocabulary, and THAT IS THE SERVER'S RULING
 * RATHER THAN A SIMPLIFICATION. `POST /review/<box>/<index>/answer` takes a `sku` that must
 * be one the pipeline offered and refuses anything else, because CLAUDE.md's hard rule —
 * never guess an identification, ambiguity goes to the review queue with its photo — would
 * otherwise be broken by hand from this screen. There is no free-text path and no
 * leave-unlisted path to bind a letter to.
 *
 * An earlier draft of this file had one. It offered "Leave unlisted" on L for the card with
 * no candidate rows, on the reasoning that such a card has exactly one thing to do and is
 * therefore where PullConfirm's solid accent fill belongs. The route says otherwise: a
 * no-candidates entry is refused as `no_candidates` and told it needs a re-shoot or a
 * re-identify, not an answer. So that card has ZERO actions here, this screen never draws
 * the fill at all, and PullConfirm is not reused — which is also the plainest possible
 * reading of docs/DESIGN.md's rule that a screen with two answers gets no fill.
 */
const SKIP_KEY = 's'
const SKIP_KEY_LABEL = 'S'

/* Clearing the skips is a choice too, so it shows its key — but only while the note that
 * offers it is on screen. A key bound permanently to a control that is drawn sometimes is a
 * key that does nothing most of the time, which is the opposite of what showing it is for. */
const CLEAR_KEY = 'c'
const CLEAR_KEY_LABEL = 'C'

/* Focus that swallows a key, the same set `trigger.ts` refuses to fire through and for the
 * same reasons — including SELECT, whose letter typeahead would otherwise both jump a list
 * and answer a card. This screen has no field today; the guard costs one function and stops
 * that from being a thing to remember when it gains one. */
function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}

// ------------------------------------------------------------------------------ the screen

/** One entry with the queue it came from. The key is prefixed because a position can appear
 *  in both files — `release` drops an entry from one queue when a later run moves it, and
 *  the two writes are not simultaneous. */
type Row = {
  key: string
  queue: QueueName
  entry: QueueEntryWire

  /** The OTHER queue holding this same position open, when there is one. Set by
   *  `oneCardPerPosition` on the row it keeps, so a card in both files can say so on screen:
   *  without it the count line reads `1 to review · 1 parked` above a single drawn row and
   *  nothing explains where the second went. */
  shadow?: QueueName
}

function rowsOf(snapshot: QueueSnapshot): Row[] {
  /* Main first, then parked, each in the order the server sent it.
   *
   * THE ORDER IS NOT RECOMPUTED HERE. `store/queues.py:open_entries` already sorts by
   * `sort_key` — priced first and descending, unpriced last, then box-walk by box and index
   * — and re-implementing that in TypeScript would be a second copy of D9's ordering that
   * nothing keeps in step, the same argument that keeps the position label off this side of
   * the wire. What this function does is concatenate, which is a decision the server cannot
   * make for it because the two queues are two files.
   *
   * Main before parked, rather than one list sorted by price across both: parked is below
   * the threshold by construction, so the two never interleave on price anyway, and D9 keeps
   * them apart precisely so an unidentifiable 15-cent card cannot get in front of a $12 one.
   */
  const open = (entries: QueueEntryWire[], queue: QueueName): Row[] =>
    entries
      .filter((entry) => !entry.cleared_by_human)
      .map((entry) => ({ key: `${queue}:${entry.position}`, queue, entry }))

  return [...open(snapshot.review, 'review'), ...open(snapshot.parked, 'parked')]
}

/** One row per POSITION, review before parked, with the dropped twin recorded on the row
 *  that survives.
 *
 *  A POSITION CAN HOLD AN OPEN ENTRY IN BOTH FILES AT ONCE. Nothing in `store/queues.py`
 *  prevents it and `do_delete_card` clears both for that reason. Drawn straight out of
 *  `rowsOf`, such a card is two cards on this screen, and answering one of them clears BOTH
 *  entries server-side: the twin is left sitting in the worklist as a card that can no longer
 *  be answered, since pressing it returns `already_answered` — a true refusal about a question
 *  nobody is being asked.
 *
 *  THE REVIEW ENTRY IS THE ONE KEPT, AND THAT IS NOW A CORRECTNESS RULE RATHER THAN A
 *  PREFERENCE. `do_review_answer` validates the answer against ONE entry's candidate rows —
 *  `holders[0]`, built review-first, so the main entry governs whenever a position is in both.
 *  This function keeps the same row for the same reason `rowsOf` emits review first, so the
 *  rows this screen offers are exactly the rows that route will accept. Flip the preference
 *  and the screen draws parked's candidates against a server governed by review's, and every
 *  answer for a card in both files comes back `sku_not_a_candidate`.
 *
 *  IT USED TO BE MERELY D9'S TASTE, and the older reason still holds underneath: main is
 *  where a card goes when its market price is at or above the threshold, and parked is the
 *  low-value queue held apart precisely so an unidentifiable 15-cent card cannot get in front
 *  of a $12 one — so keeping the parked entry would draw the cheaper of the two reasons, sort
 *  the card by the cheaper of the two prices, and dim a row the operator is actually being
 *  asked about. Both arguments point the same way, which is why the change on the server side
 *  needed no change here. The comment is what needed correcting: it claimed the route "unions
 *  their candidates", which was true when it was written and was the bug the route was
 *  repaired to stop — a stale parked entry could launder a SKU the review entry never offered
 *  onto a real card, invisibly, since afterwards it is a real row from a real catalog.
 *
 *  What is lost with the dropped row is the parked entry's reason and price, and `shadow`
 *  names the file they are in. Its candidate rows go with it, and that is the point rather
 *  than a cost: they were never answerable for this position while the review entry is open.
 */
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

/** Which queues the answer route says it cleared, or null when it did not say.
 *
 *  `POST /review/<box>/<index>/answer` reports `review_cleared` and `parked_cleared` — both
 *  true is the entry-in-both-queues case, which that route calls worth seeing rather than
 *  smoothing over. `server.ts:answerReview` types its return as the one field it names, so
 *  the flags are read off the body here rather than by widening a type in a module this
 *  screen does not own.
 *
 *  NULL IS NOT "CLEARED NOTHING", and the difference decides whether an answered card comes
 *  back on screen. A server that sends neither flag is an older server, not one that cleared
 *  less: the route clears every open entry it found or it refuses outright, so a success with
 *  no report is a success for every row this screen was holding. Reading an absent field as
 *  false would redraw a card whose answer is already written, where the only move left is to
 *  press it again and be told `already_answered`.
 */
function clearedQueues(result: unknown): ReadonlySet<QueueName> | null {
  if (typeof result !== 'object' || result === null) return null
  const body = result as { review_cleared?: unknown; parked_cleared?: unknown }
  if (typeof body.review_cleared !== 'boolean' && typeof body.parked_cleared !== 'boolean') {
    return null
  }
  const cleared = new Set<QueueName>()
  if (body.review_cleared === true) cleared.add('review')
  if (body.parked_cleared === true) cleared.add('parked')
  return cleared
}

export function ReviewQueue() {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [reloads, setReloads] = useState(0)

  /* Cards pushed to the back of this session's worklist, IN THE ORDER THEY WERE SKIPPED.
   * CLIENT-SIDE ONLY: nothing is written, the entry stays open in its queue file, and a
   * reload forgets every one of them.
   *
   * ASSUMPTION — docs/DESIGN.md specifies no such control, and it is here because two cards
   * cannot be answered at all and would otherwise stop the queue dead. A card the pipeline
   * offered no rows for is refused by the route as `no_candidates`; a card you are not ready
   * to decide has no other move, because the only write this screen can make is final —
   * `Queue.upsert` refuses to re-queue a position a human has cleared, deliberately, so that
   * an answer outlives the question. Skipping writes nothing at all: the entry stays open in
   * its file, the run report still counts it, and a reload forgets the skip. Settled by real
   * queue traffic at Gate B: if nothing is ever skipped, delete it.
   *
   * A LIST RATHER THAN A SET, AND THAT IS WHAT MAKES SKIP WRAP. A set records only THAT a
   * card was skipped, so once every open card had been skipped the back of the worklist was
   * in the server's order again and re-skipping the card at the front of it moved nothing:
   * the screen sat on one card and the key stopped doing anything. It was a dead end for
   * exactly the card that has no way out of it — the pipeline offers no candidate rows, the
   * route refuses to answer it, and skip is its only control. Re-skipping now moves a card
   * behind the others it was skipped with, so the key always advances and the loop is a loop.
   *
   * The order inside the skipped group is therefore skip order, which is an order the screen
   * can explain. That is the distinction the rejected version below turns on: rotating the
   * array reorders cards nobody touched.
   */
  const [deferred, setDeferred] = useState<readonly string[]>([])

  /* The key whose photo 404'd rather than a boolean, for PullPreview.tsx's reason: an
   * `onError` for the previous card can land after the queue has advanced, and a boolean
   * would blame the wrong card for a missing file. */
  const [photoAbsent, setPhotoAbsent] = useState<string | null>(null)

  /* An answer in flight. `busy` draws it; `busyRef` decides, because two key presses in one
   * tick would both read a stale `false` and answer two cards against one round trip. Same
   * split, for the same reason, as `CaptureScreen`'s capture guard. */
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)

  /* A queue read in flight — the first one, and every Reload after it. The same two-value
   * split, and it exists to make the two round trips this screen makes MUTUALLY EXCLUSIVE:
   * an answer is refused while a read is in flight, and Reload is disabled while an answer
   * is. A snapshot read before an answer landed can then never overwrite the rows that answer
   * changed.
   *
   * BOTH DIRECTIONS WERE REACHABLE AND EACH WAS WRONG DIFFERENTLY. Reload pressed during an
   * answer: the failure path re-inserts the card into a list the fresh snapshot already
   * carries, and the worklist grows a duplicate row for one position. Answer pressed during a
   * reload: the snapshot lands last and resurrects a card whose answer is already written,
   * which then refuses as `already_answered` when it is pressed again — a card that cannot be
   * got rid of without another reload.
   *
   * Rejected: a generation counter captured at answer time and compared in each callback,
   * which leaves both requests in flight and then throws one of the two results away. This
   * costs the operator one keystroke inside a window measured in milliseconds, and it is one
   * rule rather than a rule per callback. */
  const [loading, setLoading] = useState(true)
  const loadingRef = useRef(true)

  useEffect(() => {
    // StrictMode runs effects twice in dev and a slow first response can land after the
    // second one; the flag makes the late arrival a no-op rather than a flicker — including
    // in `finally`, so a cancelled read cannot clear a flag the live one has just set.
    let live = true
    loadingRef.current = true
    setLoading(true)
    void getQueues()
      .then(
        (snapshot) => {
          if (!live) return
          setRows(rowsOf(snapshot))
          setFailure(null)
          setPhotoAbsent(null)
          setDeferred([])
        },
        (err: unknown) => {
          if (!live) return
          setRows(null)
          setFailure(describeFailure(err))
        },
      )
      .finally(() => {
        if (!live) return
        loadingRef.current = false
        setLoading(false)
      })
    return () => {
      live = false
    }
  }, [reloads])

  /* The worklist: one row per position, everything still open, with skipped cards moved to
   * the back in skip order and the server's sort preserved inside the group that is left.
   * Rejected: rotating the array, which is one line and loses the sort — a card skipped once
   * would come back sitting between two others for no reason the screen could explain, where
   * the skipped group's order is one the screen can name.
   *
   * `allSkipped` travels with it because it is the same partition read once: everything still
   * waiting has been pushed to the back, so the next skip only moves the current card behind
   * the others and the screen has to say so rather than looking stuck. */
  const { worklist, allSkipped } = useMemo(() => {
    if (rows === null) return { worklist: [] as Row[], allSkipped: false }

    const cards = oneCardPerPosition(rows)
    const skipped = new Set(deferred)
    const held = cards.filter((row) => !skipped.has(row.key))

    /* Rebuilt from `deferred` rather than filtered out of `cards`, because the skip order is
     * the point. A key whose card has since gone — answered, or dropped by a reload — falls
     * out here, which is cheaper than pruning the list on every change to `rows`. */
    const byKey = new Map(cards.map((row) => [row.key, row]))
    const pushed = deferred.flatMap((key) => {
      const row = byKey.get(key)
      return row === undefined ? [] : [row]
    })

    return { worklist: [...held, ...pushed], allSkipped: held.length === 0 && pushed.length > 0 }
  }, [rows, deferred])

  const current = worklist[0] ?? null

  const answer = useCallback(
    (row: Row, candidate: CandidateRow) => {
      // One round trip at a time, in both directions — see `loading`.
      if (busyRef.current || loadingRef.current) return

      /* EVERY ROW AT THIS POSITION, NOT THE ONE THAT WAS PRESSED. The route clears both
       * queues for a position held in both, so dropping only the pressed row leaves a twin on
       * screen that the server has already released. The worklist merges the two into one
       * card (`oneCardPerPosition`); this is the same fact applied to the write. */
      const position = row.entry.position
      const dropped = rows === null ? [row] : rows.filter((held) => held.entry.position === position)

      /* Advance first. docs/DESIGN.md: answering writes the answer and advances, with no
       * acknowledgement to dismiss — so the next card is on screen before the write lands.
       * The card is put back if the write fails, which is the only case where the owner has
       * to look at it again.
       *
       * Answers are serialised all the same. `Store.write()` waits up to 30 seconds for the
       * file lock, so a queue answered faster than the store can commit would stack writes
       * against a lock and report their failures out of order. One in flight means the card
       * a failure names is always the card just answered. */
      const at = rows === null ? -1 : rows.findIndex((held) => held.entry.position === position)
      busyRef.current = true
      setBusy(true)
      setFailure(null)
      setRows((prev) =>
        prev === null ? prev : prev.filter((held) => held.entry.position !== position),
      )

      /* Back where they were, together. The two rows for one position are not adjacent in
       * `rows` — `rowsOf` writes every review row before the first parked one — so a restore
       * puts the parked twin beside its review row rather than at the top of the parked
       * block. That is invisible: the worklist merges them again before anything is drawn,
       * and the order that matters is the server's, which a reload restores exactly. */
      const restore = (back: Row[]) => {
        if (back.length === 0) return
        setRows((prev) => {
          if (prev === null) return back
          const next = [...prev]
          next.splice(at < 0 ? 0 : Math.min(at, next.length), 0, ...back)
          return next
        })
      }

      /* BOTH FIELDS, COPIED OFF THE ROW THAT WAS PRESSED. The route requires `condition`
       * even though the SKU implies it, and its reasoning is worth not defeating here: the
       * pair says which row this screen believes it is picking, and a disagreement means the
       * screen was drawn from a queue file a later join has rewritten. Deriving the condition
       * from the SKU on this side would hand the server a self-consistent pair every time and
       * turn a stale click into a wrong finish on a real card. */
      void answerReview({
        box: row.entry.box,
        index: row.entry.index,
        sku: candidate.sku,
        condition: candidate.condition,
      })
        .then(
          (result: unknown) => {
            /* WHAT CAME BACK, RATHER THAN WHAT THIS SCREEN ASSUMED. The route reports which
             * queues it cleared, so a row whose queue it did not name goes back on screen
             * instead of being dropped on the strength of a 200. Today the route clears every
             * open entry it finds or refuses outright, so this restores nothing — which is
             * the point of reading it rather than a reason not to: the day that stops being
             * true, the screen follows the write instead of disagreeing with it silently. */
            const cleared = clearedQueues(result)
            if (cleared !== null) restore(dropped.filter((held) => !cleared.has(held.queue)))

            /* Identity preserved when the answered card was never skipped, which is the
             * common case and the hot one: a new array on every answer would invalidate the
             * worklist memo once per card across a whole box for nothing. */
            const answered = new Set(dropped.map((held) => held.key))
            setDeferred((prev) =>
              prev.some((key) => answered.has(key)) ? prev.filter((key) => !answered.has(key)) : prev,
            )
          },
          (err: unknown) => {
            /* Loud, and back where it was. §5.5's rule for a failed capture is that the run
             * stops and says so; the same argument holds here — a card whose answer was
             * refused and which quietly left the queue is a card that will never be looked
             * at again, because nothing re-queues a position the pipeline still considers
             * resolved.
             *
             * EXCEPT FOR THE TWO CODES THAT MEAN THE CARD IS NO LONGER WAITING. The route
             * distinguishes `already_answered` — the two-device case D5 and D13 describe,
             * where the other browser or the Fulfiller's tablet got there first — from
             * `not_in_queue`, and separates them precisely because the remedies differ.
             * Neither is a card to put back: restoring one would redraw a card whose answer
             * is already written and invite a second press that fails the same way. The
             * server's own message says to reload, and the panel prints it verbatim. */
            const stale =
              err instanceof ServerError &&
              (err.code === 'already_answered' || err.code === 'not_in_queue')
            if (!stale) restore(dropped)
            setFailure(describeFailure(err))
          },
        )
        .finally(() => {
          busyRef.current = false
          setBusy(false)
        })
    },
    [rows],
  )

  const skip = useCallback((row: Row) => {
    /* Moved to the back of the skipped group rather than merely marked as skipped, so that
     * skipping the last unskipped card and skipping an already-skipped one both advance. A
     * set could only do the first, and the second is the case that mattered — see `deferred`. */
    setDeferred((prev) => [...prev.filter((key) => key !== row.key), row.key])
  }, [])

  /* Back to the server's order, with nothing written either way: a skip was never a write, so
   * un-skipping is not one either. Offered only while every waiting card is skipped, which is
   * the one state where the screen would otherwise just cycle. */
  const clearSkips = useCallback(() => setDeferred([]), [])

  /* The key map, armed once and reading the current card through a closure React rebuilds
   * whenever the card or the handlers change. Digits pick a candidate, S skips, and C clears
   * the skips for exactly as long as the note offering it is on screen. */
  useEffect(() => {
    if (current === null) return

    const onKeyDown = (event: KeyboardEvent) => {
      // A held key answering a run of cards is this screen's version of the held-undo hazard
      // docs/DESIGN.md names, and here every one of those answers is a write.
      if (event.repeat) return
      // Modifiers belong to the browser and the OS.
      if (event.metaKey || event.ctrlKey || event.altKey) return
      if (isEditableTarget(event.target)) return
      // Both flags, because a queue read in flight is about to replace every row on screen.
      if (busyRef.current || loadingRef.current) return

      const key = event.key.toLowerCase()

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
      const candidate = current.entry.candidates[digit - 1]
      if (candidate === undefined) return
      event.preventDefault()
      answer(current, candidate)
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [current, answer, skip, clearSkips, allSkipped])

  const counts = useMemo(() => {
    if (rows === null) return null
    /* THE TWO QUEUE FILES' OWN DEPTHS, not the length of the worklist. A position open in
     * both files is one card on screen and one entry in each file, so these two numbers can
     * add up to more than there are cards to work — which is the same arithmetic the run
     * report prints, and the merged row says `also parked` rather than leaving the difference
     * unexplained. */
    return {
      review: rows.filter((row) => row.queue === 'review').length,
      parked: rows.filter((row) => row.queue === 'parked').length,
    }
  }, [rows])

  return (
    <main className="review">
      <header className="review-head">
        <h1 className="review-title">Review queue</h1>
        {/* One line, and it is one line for a reason the copy does not carry: every pixel
            of chrome on this screen pushes the candidate rows further below the fold. See
            the vertical-budget note at the top of ReviewQueue.css. */}
        <p className="review-lede">
          One card at a time, worked expensive first. Answering advances; nothing asks twice.
        </p>
        <div className="review-controls">
          {/* Disabled while an answer is in flight, which is half of the mutual exclusion the
              `loading` note argues for: a snapshot read before that answer landed would
              resurrect the card it just cleared. Disabled during a read as well, because a
              second read stacked on the first is two snapshots racing to be last. */}
          <button
            className="review-reload"
            type="button"
            onClick={() => setReloads((n) => n + 1)}
            disabled={busy || loading}
          >
            Reload
          </button>
          {counts === null ? null : (
            <span className="review-count">
              {counts.review} to review · {counts.parked} parked
            </span>
          )}
        </div>
      </header>

      {/* NO UNWIRED PANEL. This screen drew one until 2026-08-13 — a note saying the routes
          existed and the client for them did not — and it is gone rather than kept for
          safety, because `getQueues` is imported at the top of this file and a build in which
          it is missing does not compile. A panel about a state the type system now forbids is
          a panel nobody will ever see and everybody has to read. */}

      {failure === null ? null : (
        <div className="review-note">
          <p className="review-note-text">{failure.message}</p>
          {/* The code beneath the sentence and never the sentence again — a greppable token,
              which is the whole of what the small line is for. */}
          <p className="review-machine">{failure.code}</p>
        </div>
      )}

      {rows === null && failure === null ? (
        <p className="review-note-text">Reading the queues.</p>
      ) : null}

      {rows !== null && worklist.length === 0 ? (
        <p className="review-note-text">Nothing is waiting. Every queued card has been answered.</p>
      ) : null}

      {/* THE END OF THE SKIP LOOP, NAMED. Skip wraps, so the screen never stops advancing —
          but a card coming round for the second time looks exactly like a card that did not
          move, and an operator who has skipped everything deserves to be told that rather
          than left to work it out from the position label. The way out is the same one that
          got him here, in reverse, and it costs nothing: no skip was ever written down. */}
      {allSkipped ? (
        <div className="review-note">
          <p className="review-note-text">
            Every card still waiting has been skipped, so skipping again only moves this one
            behind the rest. Clear the skips to work them in queue order again — nothing was
            written when you skipped them and nothing is written now.
          </p>
          <button
            className="review-action"
            type="button"
            onClick={clearSkips}
            disabled={busy || loading}
          >
            <span>Clear skips</span>
            <kbd className="review-key">{CLEAR_KEY_LABEL}</kbd>
          </button>
        </div>
      ) : null}

      {current === null ? null : (
        <Card
          row={current}
          /* One prop rather than a boolean beside a string: the controls are disabled for
              exactly the window this line is on screen, and two props is two chances for
              those to fall out of step. */
          activity={busy ? 'writing the answer' : loading ? 'rereading the queues' : null}
          photoAbsent={photoAbsent === current.key}
          onPhotoAbsent={() => setPhotoAbsent(current.key)}
          onChoose={(candidate) => answer(current, candidate)}
          onSkip={() => skip(current)}
        />
      )}

      {worklist.length === 0 ? null : (
        <Waiting rows={worklist} currentKey={current?.key ?? null} deferred={deferred} />
      )}
    </main>
  )
}

// -------------------------------------------------------------------------- the one card

type CardProps = {
  row: Row

  /** What the screen is waiting on, in the words the busy line prints, or null when it is
   *  waiting on nothing. Every control here is disabled for exactly that window. */
  activity: string | null
  photoAbsent: boolean
  onPhotoAbsent: () => void
  /** The whole row, not its SKU. The route wants `sku` and `condition` copied off one
   *  offered row and checks that they agree, so handing the choice down as a SKU alone would
   *  make the caller look the condition back up — which is the derivation the route exists
   *  to refuse. */
  onChoose: (candidate: CandidateRow) => void
  onSkip: () => void
}

/* Photo first, then the finding, then the rows. Single column, so the same layout works on a
 * laptop and a phone — docs/DESIGN.md rejects a left/right split by name. */
function Card({ row, activity, photoAbsent, onPhotoAbsent, onChoose, onSkip }: CardProps) {
  const { entry } = row
  const parts = sentence(entry)
  const busy = activity !== null

  /* NO SOLID ACCENT FILL ANYWHERE ON THIS SCREEN, and it took building the thing to see that
   * this is the plain reading rather than a gap.
   *
   * docs/DESIGN.md gives accent two jobs and reserves the fill for a screen with exactly one
   * thing to do; a screen with two answers gets no fill, because every way of choosing which
   * answer to fill is biased — the pricier candidate teaches the queue to drift toward
   * over-listing, and the toggle's answer makes the fill mean two different things on two
   * screens. Candidate rows are therefore outlined, however many there are.
   *
   * The draft before this one found what looked like the exception: a card with NO candidate
   * rows has nothing to choose between, so "leave it unlisted" would be its one action and
   * would earn the fill. The route disagrees, and it is right — `POST /review/.../answer`
   * refuses a no-candidates entry as `no_candidates` and says it needs a re-shoot or a
   * re-identify. That card has zero answers here, not one. So the fill has no home on this
   * screen and PullConfirm is not reused: it stays the Fulfiller's loudest control, which is
   * what docs/DESIGN.md says it is for.
   */

  return (
    <section className="review-card">
      <Photo row={row} absent={photoAbsent} onAbsent={onPhotoAbsent} />

      <p className="review-position">{entry.label}</p>

      <div className="review-reason">
        {/* Accent at outline and text weight: the system is unsure. The chip carries the
            human label; the machine string sits beneath it, lowercase and unstyled beyond
            the utility face, because it has to grep against the run report and review.json
            exactly as it reads here. */}
        <p className="review-reason-label">{reasonLabel(entry.reason)}</p>
        <p className="review-machine">{entry.reason}</p>
      </div>

      <p className="review-sentence">
        {parts.map((part, at) => {
          if (part.kind === 'text') return <span key={at}>{part.text}</span>
          return (
            <span key={at} className={part.kind === 'claim' ? 'review-claim' : 'review-value'}>
              {part.text}
            </span>
          )
        })}
      </p>

      {entry.candidates.length === 0 ? (
        /* The card that cannot be answered here, and the copy says so plainly rather than
           drawing an empty list. `cli/resolve.py:failure_entry` records no candidates for an
           identification that failed or a card with no position, and the route refuses such
           an entry as `no_candidates` — so the remedy is a re-shoot or a re-identify, and the
           only move on this screen is to skip past it. Rejected: hiding the card, which would
           make a queue count that never goes down with nothing on screen to explain it.

           THE COPY NAMES WHERE THE REMEDY IS, because skip is not one. Skip moves the card
           and writes nothing; the entry stays open in its file whatever this screen does, so
           a sentence that stopped at "skip past it" described a loop rather than a way out.
           The way out is a command in a terminal, and it is worth one clause to say so. */
        <p className="review-note-text">
          The pipeline offered no rows for this card, so there is nothing here to choose, and
          the answer route refuses it rather than inventing one. It needs another photograph or
          another identification run — neither of which happens on this screen. Skip moves it
          behind the rest of the worklist and writes nothing; the entry stays open in its queue
          file until a later run replaces it.
        </p>
      ) : (
        <ul className="review-candidates">
          {entry.candidates.map((candidate, at) => (
            <li key={`${candidate.sku}:${at}`}>
              {/* Not filled, and not sorted here either. These are the rows the card COULD
                  be, in the order the export listed them; re-ordering them by price would
                  imply a ranking the list does not have and would put the expensive one under
                  the first key. */}
              <button
                className="review-candidate"
                type="button"
                onClick={() => onChoose(candidate)}
                disabled={busy}
              >
                {at < MAX_KEYED_CANDIDATES ? (
                  <kbd className="review-key">{at + 1}</kbd>
                ) : (
                  <span className="review-key-blank" aria-hidden="true" />
                )}
                <span className="review-candidate-name">{candidate.name}</span>
                <span className="review-candidate-condition">{candidate.condition}</span>
                {/* Quieted when there is no price, and ONLY the price cell — the same
                    treatment the worklist gives an unpriced row, for the same reason. A
                    missing price is an unknown price (D9), so the row itself must not shrink
                    as though the card were cheap; the words standing in for the number are
                    just not a number and should not be set like one. */}
                <span
                  className={
                    priceOf(candidate.market) === null
                      ? 'review-candidate-price is-unpriced'
                      : 'review-candidate-price'
                  }
                >
                  {priceText(candidate.market)}
                </span>
                <span className="review-candidate-meta">
                  {candidate.set} · {candidate.number} · SKU {candidate.sku}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="review-actions">
        {/* Skip is the only control on this screen that is not a candidate row, and it is the
            only way past a card that cannot be answered — see the no-candidates note above.
            Quiet by construction: it writes nothing, so it must not look like an answer. */}
        <button className="review-action" type="button" onClick={onSkip} disabled={busy}>
          <span>Skip</span>
          <kbd className="review-key">{SKIP_KEY_LABEL}</kbd>
        </button>

        {/* Not a spinner and not a disabled-everything overlay: a line that says which state
            the screen is in, in the utility face, because it is a state and not a sentence.
            The controls above carry `disabled` for the same window. It names the round trip
            rather than saying "busy" — writing an answer and rereading the queues lock the
            same controls and mean opposite things about whether your last press landed. */}
        {activity === null ? null : <span className="review-busy">{activity}</span>}
      </div>

      {/* LAST, AND IT WAS BETWEEN THE SENTENCE AND THE CANDIDATES UNTIL THIS WAS RENDERED
          AND LOOKED AT. docs/DESIGN.md gives this screen an order — photo, then one sentence
          naming what the system found, then the candidate rows with their prices — and nine
          rows of metadata in the middle of it pushed every answer below the fold. The facts
          are worth having on the screen the owner debugs a run from; they are not worth
          standing between the finding and the choice. */}
      <Facts row={row} />
    </section>
  )
}

// ------------------------------------------------------------------------------ the facts

/* Everything the run knows about this card that the sentence did not say. The utility face
 * throughout except the card's name, which is a thing a human reads — docs/DESIGN.md's
 * mono-carries-all-metadata rule applied one field at a time, exactly as PullPreview does it. */
function Facts({ row }: { row: Row }) {
  const { entry } = row
  const facts: { label: string; value: string; body?: boolean }[] = [
    { label: 'Card', value: text(entry.read.name) ?? 'not identified', body: text(entry.read.name) !== null },
    { label: 'Number', value: collectorNumber(entry.read) ?? 'none' },
    { label: 'Market', value: priceText(entry.market) },
    /* Both files when both hold this position open. The worklist draws one card and the count
     * line counts two entries; this is the line that reconciles them, and a card queued twice
     * is worth seeing rather than smoothing over — the same call `do_review_answer` makes when
     * it reports each queue it cleared separately. */
    { label: 'Queue', value: row.shadow === undefined ? row.queue : `${row.queue} · ${row.shadow}` },
    { label: 'Confidence', value: text(entry.confidence) ?? 'none recorded' },
    { label: 'Set hint', value: text(entry.read.set_hint) ?? 'none' },
    { label: 'Toggle', value: text(entry.read.metadata_finish) ?? 'no claim' },
    { label: 'Read finish', value: text(entry.read.detected_finish) ?? 'none' },
    { label: 'Waiting', value: seenText(entry) },
  ]

  return (
    <dl className="review-facts">
      {facts.map((fact) => (
        <div className="review-fact" key={fact.label}>
          <dt>{fact.label}</dt>
          <dd className={fact.body === true ? 'is-body' : undefined}>{fact.value}</dd>
        </div>
      ))}
    </dl>
  )
}

// ------------------------------------------------------------------------------ the photo

/* D4: the review queue shows the stored capture photo beside candidate catalog rows for a
 * one-tap choice, and the physical card never leaves its box. D6 is the route that serves it.
 *
 * Three ways it can be absent, and they are different facts rather than one broken image:
 * the entry was never given a photo, the entry has no position to serve one from (box 0 is
 * `cli/resolve.py`'s marker for a pre-join failure, since D10 starts at 1), or the file is
 * gone from disk. Each says which, and prints what was asked for. */
function Photo({ row, absent, onAbsent }: { row: Row; absent: boolean; onAbsent: () => void }) {
  const { entry } = row

  if (entry.box < 1) {
    return (
      <div className="review-absent">
        <p className="review-note-text">
          This entry has no position, so there is no stored photograph to show. It reached the
          queue before it was given one.
        </p>
        <p className="review-machine">box {entry.box} · index {entry.index}</p>
      </div>
    )
  }

  if (entry.photo === null) {
    return (
      <div className="review-absent">
        <p className="review-note-text">No photograph was stored for this card.</p>
        <p className="review-machine">photo: null</p>
      </div>
    )
  }

  const src = photoUrl(entry.box, entry.index)

  if (absent) {
    return (
      <div className="review-absent">
        <p className="review-note-text">
          The entry has a photograph and the file is not on disk. Nothing here can restore it —
          the card is still at {entry.label}.
        </p>
        <p className="review-machine">{src}</p>
      </div>
    )
  }

  return (
    <img
      // Remounted per card, so a failed load cannot leave the previous card's broken state
      // attached to the next one's element.
      key={row.key}
      className="review-photo"
      src={src}
      alt={`The card photographed at ${entry.label}`}
      onError={onAbsent}
    />
  )
}

// ------------------------------------------------------------------------- what is waiting

/* "Worked expensive-first, and that ordering has to be visible."
 *
 * The sort is real and runs today — `store/queues.py:sort_key`, priced first and descending,
 * unpriced last, then box-walk order. This list is the only place the screen SHOWS it, and
 * docs/DESIGN.md is explicit that showing it is not the same as obeying it: the row's name
 * size and its price size both step down as the price does, and a parked row is dimmed rather
 * than merely lower. A queue where every row looks equally important has thrown away a sort
 * it already has.
 *
 * DISPLAY ONLY — no row is pressable. Making them navigable would be a list -> detail -> back
 * loop, which docs/DESIGN.md forbids by name, and it would also be pointless: the worklist is
 * an order, and the way past a card is to answer it or to skip it.
 */
function Waiting({
  rows,
  currentKey,
  deferred,
}: {
  rows: Row[]
  currentKey: string | null
  /** In skip order, which is the order the tail of this list is in. */
  deferred: readonly string[]
}) {
  return (
    <section className="review-waiting">
      <h2 className="review-waiting-title">Waiting</h2>
      <ul className="review-waiting-list">
        {rows.map((row) => (
          <li
            key={row.key}
            className="review-row"
            data-band={bandOf(row.entry.market)}
            data-parked={row.queue === 'parked' ? 'true' : undefined}
            aria-current={row.key === currentKey ? 'true' : undefined}
          >
            <span className="review-row-name">{text(row.entry.read.name) ?? 'not identified'}</span>
            <span className="review-row-price">{priceText(row.entry.market)}</span>
            <span className="review-row-position">{row.entry.label}</span>
            <span className="review-row-reason">
              {row.entry.reason}
              {/* The queue that lost the merge, named on the row rather than only in the
                  facts panel: this list is where the count line is read against the rows, and
                  it is the only place a card queued twice can be seen at all once it is not
                  the card being worked. */}
              {row.shadow === undefined ? '' : ` · also ${row.shadow}`}
              {deferred.includes(row.key) ? ' · skipped' : ''}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
