import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { isEditableTarget } from './keys'
import type {
  AnswerResult,
  CandidateRow,
  QueueEntryWire,
  QueueName,
  QueueRead,
  QueueSnapshot,
} from './types'
import type { Failure } from './server'
import {
  ServerError,
  answerReview,
  describeFailure,
  getQueues,
  photoUrl,
  undoAnswer,
} from './server'
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
 * branch, and this paragraph used to end "THE DATA THIS SCREEN DISPLAYS HAS NEVER EXISTED".
 *
 * IT EXISTS NOW. Gate B ran 53 cards on 2026-08-22, put 16 real entries in the parked queue,
 * and the owner answered every one of them on this screen. What that settled and what it did
 * not is in docs/GATES.md; the short form for a reader of this file is that the entry shape,
 * the candidate shape, the sort and the answer route all held, and that the one number this
 * file invents did not get its measurement — the whole run priced $0.04 to $0.40, so every
 * card landed in one band and the price-driven type scale was never asked to separate
 * anything. The bands are still marked as an assumption at the place they are cut, and what
 * they now wait on is a MIXED-VALUE lot rather than merely another run.
 *
 * Nothing else here is invented: the reason strings, the entry shape, the candidate shape,
 * the sort and the two-queue split are all read out of the modules that produce them, and
 * the answer's shape is read out of the route that takes it.
 *
 * WHAT THE RUN CHANGED IN THIS FILE IS D28. Answering was irreversible — `Queue.upsert`
 * refuses to re-queue a position a human has cleared — and it was the one action in the
 * product with no photo to confirm against, no undo and no acknowledgement, while mark-sold,
 * which reverses, has all three. D28 orders two fixes: stop the list moving under the finger,
 * and give the answer a twenty-second undo. BOTH ARE HERE NOW. The first is the reserved photo
 * frame and the prefetch; the second is the receipt, `UNDO_KEY`, and `Queue.reopen` behind
 * `{"undo": true}` on the answer route.
 *
 * THE UNDO DOES NOT SOFTEN `Queue.upsert`'s REFUSAL AND IS NOT MEANT TO. That refusal is about
 * a later RUN re-asking a settled question; this is the same person reversing himself inside a
 * window. D28 calls it a hole punched in the rule on purpose, and `store/queues.py:reopen` is
 * how narrow the hole is.
 *
 * TWO ROUTES, ONE OF THEM TWO-WAY, in `server/capture_server.py`:
 *
 *   GET  /queues                      both standing queues, already in worked order
 *   POST /review/<box>/<index>/answer one candidate row, chosen  (D4) — or `{"undo": true}`,
 *                                     which takes that answer back and puts the card in the
 *                                     queue again (D28)
 *
 * The second one settled a question this screen had guessed at and guessed wrong. An earlier
 * draft offered "Leave unlisted" as a way to clear a card without picking a row; the route
 * has no such path, refuses an entry with no candidates outright, and requires `condition`
 * alongside `sku` so that a stale screen is caught rather than obeyed. Both are recorded at
 * the code they changed rather than only here.
 *
 * WHAT IS NOT HERE, and deliberately: no confirm dialog, no acknowledgement to dismiss, no
 * list -> detail -> back loop. docs/DESIGN.md forbids all three by name and D28 declines a
 * modifier or an Enter on the answer in as many words — one key per card is the property being
 * protected. Answering writes the answer and advances.
 *
 * THE RECEIPT IS NOT THE ACKNOWLEDGEMENT THAT RULE BANS, and the difference is the word
 * "dismiss". Nothing has to be pressed to get past it: it appears below the candidate rows
 * where it cannot move one, it expires on its own, and the next card is already on screen and
 * answerable underneath it. What it carries is a control that did not exist before, which is
 * the whole of what D28 reopened that rule for — the rule's own justification is "Undo covers
 * the mistake", and on this screen undo did not exist.
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
 * The labels are still the least tested copy in the product, and Gate B narrowed that rather
 * than closing it. Exactly one of the twelve has fired against a photograph of a card:
 * `metadata_detection_disagreement`, 16 times out of 53, which is 16 cards' worth of evidence
 * for one label and none at all for the other eleven. (`no_catalog_row` fired 23 times against
 * a commons-only export and zero times against the full one, which is a fact about the export
 * rather than about the label.) A label written for a code that fires weekly and one written
 * for a code that fires once a year are different pieces of copy, and after a real run the
 * only one this repo can tell apart is the first.
 */
const REASON_LABELS: Readonly<Record<string, string>> = {
  // pipeline/variant.py — the ladder could not settle the finish.
  no_catalog_row: 'Not in the export',
  metadata_not_stocked: 'Toggle names a finish that is not stocked',
  metadata_detection_disagreement: 'Toggle and photo disagree',
  /* D23's stack claim contradicted the catalog: every candidate row's Rarity sits outside
   * what the operator claimed the stack holds. Deliberately NOT `metadata_*` — those three
   * are about the finish toggle, and a fourth reading as one at a glance is why the name
   * was rejected (D23 records it). */
  rarity_claim_mismatch: 'Claimed rarities match no row',
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

/* Reload had no key until 2026-08-22, on a screen whose whole argument for showing keys is
 * that an hour in this queue is a keyboard and not a mouse. It is the prescribed remedy for
 * every one of the four refusals in STALE_CODES below — each of those messages ends by
 * telling the operator to reload the queue — so the one control the server names by name was
 * the one control that made him find the pointer to obey it.
 *
 * ARMED EVEN WHEN THERE IS NO CARD ON SCREEN, which is not an edge case but the state that
 * needs it most: a `GET /queues` that failed draws no card at all, and the key handler used
 * to return before binding anything when `current` was null. So the reload branch sits above
 * that guard and every other branch sits below it. */
const RELOAD_KEY = 'r'
const RELOAD_KEY_LABEL = 'R'

/* Take the last answer back (D28). ARMED WITH NO CARD ON SCREEN, like reload and for a sharper
 * version of the same reason: the answer that most wants taking back is often the one that
 * emptied the queue, and a control that disappears at the moment it is needed is not a control.
 *
 * IT ACTS ON THE NEWEST RECEIPT STILL STANDING and never on the card in front of you, which is
 * the one thing about it worth being careful with. Every other key on this screen is about the
 * current card; this one is about the previous one. That is unavoidable — the answered card has
 * left the screen by construction, because answering advances — and it is why the receipt draws
 * the position it is about beside the key rather than trusting the operator to remember.
 *
 * ONE KEY AND NOT ONE PER RECEIPT. Older receipts are answered with the mouse and draw a dash
 * where the chip goes, the same treatment `MAX_KEYED_CANDIDATES` gives a tenth candidate row
 * and for the same reason: a blank column reads as a chip that failed to render. Digits are
 * spoken for by the candidate rows, so numbering the receipts is not available even if a stack
 * deep enough to want it ever appeared. */
const UNDO_KEY = 'u'
const UNDO_KEY_LABEL = 'U'

/* Twenty seconds, and it is not a number this file chose: `Fulfillment.tsx:UNDO_WINDOW_MS` is
 * the same value on the same product for the same job, and D28 asks for "the shape the product
 * already ships" rather than a second one.
 *
 * THE CLOCK IS HELD HERE AND NOT BY THE SERVER, which is the owner's ruling taken on the day —
 * screen-held now, server-enforced only if it bites — and it matches mark-sold exactly:
 * `POST /review/<box>/<index>/answer` has no expiry, because a deadline down there fails the
 * reversal precisely when the store is slow to lock. What the twenty seconds govern is how long
 * the control stays on screen.
 *
 * WHAT THAT COSTS, RECORDED RATHER THAN DISCOVERED. Two things, both accepted:
 *
 *   it does not survive a reload   The receipts live in component state, so a refresh, a route
 *                                  change or a crash takes every standing undo with it. The
 *                                  answer is written and the card stays answered; what is lost
 *                                  is the way back. The trigger for revisiting is the first
 *                                  answer actually lost that way, and the fix would be a
 *                                  deadline on the `answered` history line rather than a
 *                                  longer window here.
 *   the other device knows nothing A browser that never saw the answer never draws its undo
 *                                  (D13: two devices, one store, no session between them). The
 *                                  route would accept the reversal from either; only this
 *                                  screen decides to offer it.
 */
const UNDO_WINDOW_MS = 20_000


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

/* THE FOUR REFUSALS THAT MEAN THIS SCREEN IS HOLDING A QUEUE THE SERVER HAS MOVED PAST.
 * Two kinds, and the difference is where the card is rather than what the screen should do:
 *
 *   already_answered      the entry is cleared and gone from the file. The two-device case
 *   not_in_queue          D5 and D13 describe, or a client asking about the wrong card.
 *                         There is nothing left to put back.
 *
 *   sku_not_a_candidate   the entry is STILL OPEN and this screen is drawing the wrong rows
 *   condition_mismatch    for it — a later join rewrote the queue file after the snapshot was
 *                         taken, so the SKU and condition copied off the row that was pressed
 *                         are not the pair `do_review_answer` will accept.
 *
 * THE SECOND PAIR IS WHY THIS IS A SET AND NOT THE TWO-CODE TEST IT REPLACES, and it was a
 * repeat-failure trap rather than a cosmetic gap. Those two refusals restored the card, which
 * put it straight back under the same finger with the same digits over the same rows the
 * server had just refused: press 1, refused, press 1, refused, for as long as the snapshot is
 * held. A screen can inflict that indefinitely, and every press looks like a fresh attempt.
 *
 * DROPPING SUCH A CARD IS NOT THE SILENT LOSS THE RESTORE EXISTS TO PREVENT, which is the one
 * thing worth being exact about here. That rule is about a card leaving the queue with nothing
 * written and nothing re-queueing it. Here the entry is still open in its file — no answer was
 * written, `Queue.upsert` has cleared nothing — so the Reload the server's own message asks for
 * brings the card back with the rows the route will actually take. What may not happen is the
 * card being dropped and the remedy being left to a control the operator has to go and find,
 * which is why RELOAD_KEY exists and why the refusal panel draws its own Reload button.
 */
const STALE_CODES: ReadonlySet<string> = new Set([
  'already_answered',
  'not_in_queue',
  'sku_not_a_candidate',
  'condition_mismatch',
])

function isStale(err: unknown): boolean {
  return err instanceof ServerError && STALE_CODES.has(err.code)
}

/* ---------------------------------------------------------------------------- the undo
 *
 * D28. Pressing a digit writes a SKU and a condition onto a real card, and `Queue.upsert`
 * refuses to re-queue a position a human has cleared — so until 2026-08-23 the one
 * irreversible action in this product had no photo to confirm against, no acknowledgement and
 * no way back, while mark-sold, which reverses, had all three. This section is the way back.
 *
 * NO CONFIRM DIALOG CAME WITH IT AND NONE MAY. docs/DESIGN.md forbids one by name and D28
 * rejects requiring a modifier or an Enter in as many words: one key per card is the property
 * being protected, and doubling the keystrokes on the screen the owner spends the most hours
 * in is exactly what the no-dialog rule exists to prevent. What D28 reopens is the
 * no-acknowledgement rule, and only for this screen — on the grounds that the rule's own
 * justification is "Undo covers the mistake", which was leaning on something that did not
 * exist here.
 */

/** Whether the answer just written can be taken back, out of the server's own answer.
 *
 *  ABSENT IS READ AS NULL, the same guard `Fulfillment.tsx:canTakeBack` states for the sale and
 *  in the same direction. A server old enough to answer this route without the field arrives as
 *  `undefined` and would typecheck as an object, and this app casts rather than validates.
 *  Suppressing an undo that would have worked costs one reload; offering one that cannot work
 *  is the defect the field exists to remove.
 *
 *  THE OBJECT, NEVER ITS MEMBERS. `restores_to` is `{sku, condition}` and BOTH are null for the
 *  ordinary queued card, which has never carried a SKU — that is why it is in a queue. Testing
 *  for a non-empty string here would suppress the undo on almost every card in a real queue,
 *  which is the reverse of the sale's shape and the one place these two readers differ. */
function canTakeBack(result: AnswerResult): boolean {
  const origin: unknown = result.restores_to
  return typeof origin === 'object' && origin !== null
}

/* THE REFUSALS AFTER WHICH THE UNDO CONTROL COMES DOWN, because pressing it again answers
 * identically forever. Four, and they divide the same way STALE_CODES does:
 *
 *   not_answered   there is no answer standing. The other device reversed it first (D5, D13),
 *   not_in_queue   or a later run released the entry outright. Either way it is done.
 *
 *   undo_too_late          a refusal with a remedy the operator owns but cannot reach from
 *   answer_origin_unknown   here: pull the listing on TCGplayer, or repair the log. The
 *                           server's message names both, the panel prints it verbatim, and
 *                           leaving the button up would only invite him to press it again.
 *
 * Everything else — a dead server, a `store_busy` behind a running join — is worth another
 * press, so the receipt stays until its own twenty seconds run out. Same instinct as
 * `Fulfillment.tsx`'s `sold_origin_unknown` ruling: a control with no remaining outcome is
 * worse than no control, because it reads as one he failed to use correctly. */
const FINAL_UNDO_CODES: ReadonlySet<string> = new Set([
  'not_answered',
  'not_in_queue',
  'undo_too_late',
  'answer_origin_unknown',
])

function isFinalRefusal(err: unknown): boolean {
  return err instanceof ServerError && FINAL_UNDO_CODES.has(err.code)
}

/** One answer that can still be taken back, and everything needed to put the card back.
 *
 *  A LIST OF THESE AND NOT ONE SLOT, which `Fulfillment.tsx` learned the expensive way: a
 *  second sale silently discarded the first card's undo and re-armed the clock for the new one.
 *  This screen answers faster than that one sells, so a single slot would throw away a window
 *  the operator had barely begun to notice he needed. Each receipt carries its own deadline, so
 *  a second answer cannot extend or shorten the first card's.
 *
 *  IT HOLDS THE ROWS RATHER THAN RE-READING THEM. The undo puts the card back on screen from
 *  what was dropped, at the index it was dropped from, which is exact and costs no round trip —
 *  the server reopened the same entry with the same candidates, so a `GET /queues` would answer
 *  with what is already in hand and would additionally undo every skip. */
type Receipt = {
  /** `Row.entry.position`. A second answer at one position replaces its receipt rather than
   *  stacking one on it, which cannot happen today — the entry is cleared in between — and is
   *  the same rule `Fulfillment.tsx` states for a second sale of one position. */
  key: string
  box: number
  index: number

  /** The server's own rendered label, for the machine line. Never composed here (D10). */
  label: string

  /** Every row this answer dropped — both, for a position open in two queue files — and the
   *  index in `rows` they were spliced out of. */
  dropped: Row[]
  at: number

  /** The sentence. "Answer" is the action, so the receipt says "Answered", which is
   *  docs/DESIGN.md's rule that an action keeps its name through the whole flow. */
  said: string

  /** Wall-clock deadline, fixed when the answer lands and never touched again. A duration held
   *  here instead would have to be restarted on every re-render. */
  until: number
}

/** A refusal, with the card it was about.
 *
 *  THE LABEL IS CAPTURED AT THE MOMENT OF THE FAILURE AND NOT READ OFF THE CURRENT CARD.
 *  Answering advances before the write lands, so by the time a refusal arrives the card on
 *  screen is usually the NEXT one — and for a stale code the refused card is not restored, so
 *  the panel is drawn beneath a card it is not about. The server's own message names the box
 *  and index for its own refusals; `client_bug` names nothing, and neither does a glance. One
 *  position label under the code is what makes the panel readable where it is drawn. Null when
 *  the failure belongs to no card, which is every failure of `GET /queues`. */
type Refusal = { failure: Failure; at: string | null }

export function ReviewQueue() {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [refusal, setRefusal] = useState<Refusal | null>(null)
  const [reloads, setReloads] = useState(0)

  /* Cards pushed to the back of this session's worklist, IN THE ORDER THEY WERE SKIPPED.
   * CLIENT-SIDE ONLY: nothing is written, the entry stays open in its queue file, and a
   * reload forgets every one of them.
   *
   * ASSUMPTION — docs/DESIGN.md specifies no such control, and it is here because two cards
   * cannot be answered at all and would otherwise stop the queue dead. A card the pipeline
   * offered no rows for is refused by the route as `no_candidates`; a card you are not ready
   * to decide has no other move, because the only write this screen can make settles the
   * question — `Queue.upsert` refuses to re-queue a position a human has cleared, deliberately,
   * so that an answer outlives the question. Skipping writes nothing at all: the entry stays
   * open in its file, the run report still counts it, and a reload forgets the skip.
   *
   * D28's UNDO DOES NOT REPLACE THIS, and it is worth saying which of the two arguments above
   * it touches. An answer is reversible for twenty seconds now, so "final" became "final once
   * the window closes" — but the card with no candidate rows still cannot be answered at all,
   * and a card you are not ready to rule on is not helped by being able to un-rule for twenty
   * seconds. Skip is still the only move for both, and the question below is still open.
   *
   * GATE B WAS NAMED HERE AS WHAT SETTLES IT AND DID NOT SETTLE IT. The run produced a real
   * 16-card queue and the owner answered all 16 in one sitting, but nothing counted how many
   * he skipped first — the instrument was never read, so the control is exactly as unsettled
   * as it was, minus one opportunity. docs/DESIGN.md records that as the mistake to not repeat:
   * counting skips has to be decided on BEFORE the next real queue session rather than noticed
   * afterwards. If nothing is ever skipped, delete this. If most of a queue is, the screen
   * needs a real defer that records a reason, and that is a decision entry rather than a
   * button.
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

  /* Answers still inside their twenty seconds (D28), newest first. See `Receipt` for why this
   * is a list, and `UNDO_WINDOW_MS` for what a screen-held clock costs.
   *
   * NEWEST FIRST, which is the opposite of every other list on this screen and is right for the
   * same reason `Fulfillment.tsx` orders its receipts that way: everything else here is a
   * worklist in the server's sort, and these are events. The answer most likely to want taking
   * back is the one just made, and `UNDO_KEY` acts on the head of this array. */
  const [receipts, setReceipts] = useState<readonly Receipt[]>([])

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
    /* `.then(ok).catch(fail)` AND NOT `.then(ok, fail)`. The two-argument form does not cover
     * its own success handler: `rowsOf` walks two queue files off the wire and coerces as it
     * goes, so a body this screen cannot read throws inside the handler and lands as an
     * unhandled rejection rather than in the panel three lines down. What that costs here is
     * worse than a blank screen — `.finally` still runs, so `loading` clears and the screen
     * looks ready while `rows` stays null and `failure` stays null, which is the "Reading the
     * queue." state with no failure shown and no control to press. Fulfillment.tsx recorded
     * that symptom in those words; the eslint rule in `app/eslint.config.js` is what stops it
     * being rediscovered a fourth time. */
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
        /* No label: this failure is about the read and not about a card. See `Refusal`. */
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

  /* Put dropped rows back where they came from. Two callers now — a refused answer, and an
   * answer taken back inside its window — which is why it stopped being a closure inside
   * `answer` and became one function.
   *
   * BOTH ROWS FOR A POSITION GO BACK TOGETHER AND NOT ADJACENTLY. `rowsOf` writes every review
   * row before the first parked one, so a restore puts the parked twin beside its review row
   * rather than at the top of the parked block. That is invisible: `oneCardPerPosition` merges
   * them again before anything is drawn, and the order that matters is the server's, which a
   * reload restores exactly.
   *
   * THE INDEX IS CLAMPED RATHER THAN TRUSTED, and after a Reload it is only approximately
   * right: `rows` has been replaced by a fresh snapshot that does not contain the answered card
   * at all, so a card put back then lands near where it used to be instead of in the server's
   * sort. Accepted rather than solved — the alternative is re-reading the queues on every undo,
   * which would also forget every skip — and R puts the sort back for the price of one press. */
  const putBack = useCallback((back: Row[], at: number) => {
    if (back.length === 0) return
    setRows((prev) => {
      if (prev === null) return [...back]
      const next = [...prev]
      next.splice(at < 0 ? 0 : Math.min(at, next.length), 0, ...back)
      return next
    })
  }, [])

  /** Stand a receipt up for one answer. A position answered twice replaces its own rather than
   *  stacking, which cannot happen while the entry is cleared in between and is the same rule
   *  `Fulfillment.tsx` states for a second sale of one position. */
  const remember = useCallback((receipt: Omit<Receipt, 'until'>) => {
    setReceipts((held) => [
      { ...receipt, until: Date.now() + UNDO_WINDOW_MS },
      ...held.filter((standing) => standing.key !== receipt.key),
    ])
  }, [])

  /* ONE TIMER FOR THE WHOLE LIST, armed at the soonest deadline rather than one per receipt —
   * `Fulfillment.tsx`'s shape, and the reasoning transfers unchanged. Each receipt carries its
   * own `until`, so this cannot re-arm anybody's window: it fires at the front of the queue,
   * drops whatever has actually expired, and the state change arms it again for the next one.
   * The 25ms of slack is what stops a timer firing a hair early from dropping nothing,
   * returning the same array, and leaving the panel up forever — React bails out on an
   * identical reference, so nothing would re-arm it. */
  useEffect(() => {
    if (receipts.length === 0) return
    const soonest = Math.min(...receipts.map((receipt) => receipt.until))
    const timer = window.setTimeout(
      () =>
        setReceipts((held) => {
          const standing = held.filter((receipt) => receipt.until > Date.now())
          return standing.length === held.length ? held : standing
        }),
      Math.max(0, soonest - Date.now()) + 25,
    )
    return () => window.clearTimeout(timer)
  }, [receipts])

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
      setRefusal(null)
      setRows((prev) =>
        prev === null ? prev : prev.filter((held) => held.entry.position !== position),
      )

      /* Back where they were, together — see `putBack`, which two callers share now that an
       * answer can also be taken back on purpose. */
      const restore = (back: Row[]) => putBack(back, at)

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
        /* `.then(ok).catch(fail)` AND NOT `.then(ok, fail)`, and this is the one of the four
         * where the two forms are not merely differently safe. The success handler below
         * walks a body the route is free to change — `clearedQueues` reads an `unknown` and
         * that is the point of it — so under the two-argument form a shape it cannot parse
         * threw past both handlers: the card stayed dropped from `rows` on the strength of a
         * write nobody had confirmed, no failure was shown, and `.finally` cleared `busy` so
         * the screen carried on to the next card as though the answer had landed. A card that
         * silently leaves this queue is a card nothing re-queues, because the pipeline still
         * considers the position resolved — which is the exact loss the failure handler two
         * screens down is written to prevent.
         *
         * `.catch` NOW ALSO COVERS THE SUCCESS HANDLER, WHICH IS THE FIX AND NOT A SIDE
         * EFFECT. Worth being exact about the one interaction: `clearedQueues` runs before
         * anything is restored, so the common throw restores cleanly. A throw after `restore`
         * has already run would restore twice, and that is invisible rather than merely rare
         * — `oneCardPerPosition` merges every row for a position before the worklist is
         * drawn, which is the same guard that lets a two-queue position be dropped and put
         * back as a pair. */
        .then((result: unknown) => {
          /* WHAT CAME BACK, RATHER THAN WHAT THIS SCREEN ASSUMED. The route reports which
           * queues it cleared, so a row whose queue it did not name goes back on screen
           * instead of being dropped on the strength of a 200. Today the route clears every
           * open entry it finds or refuses outright, so this restores nothing — which is
           * the point of reading it rather than a reason not to: the day that stops being
           * true, the screen follows the write instead of disagreeing with it silently. */
          const cleared = clearedQueues(result)
          const kept = cleared === null ? [] : dropped.filter((held) => !cleared.has(held.queue))
          if (kept.length > 0) restore(kept)

          /* THE RECEIPT, AND ONLY WHEN THE SERVER SAYS THE ANSWER CAN COME BACK (D28).
           * `restores_to` is null for an answer the route has already decided it will refuse to
           * reverse — the SKU is out of this Mac, or the log cannot say what the answer replaced
           * — and a control whose only outcome is that refusal is the defect `SaleResult`
           * records as having shipped twice. So the check is on the server's answer and never on
           * this screen's optimism.
           *
           * A CARD THE SERVER DID NOT FULLY CLEAR GETS NO RECEIPT EITHER. `kept` is the rows put
           * straight back on screen, and offering an undo for a card that is still in the
           * worklist would be two ways to reach one state. It cannot happen today — the route
           * clears every open entry it finds or refuses outright — which is exactly why it is
           * cheap to be correct about now rather than the day that changes. */
          if (kept.length === 0 && canTakeBack(result as AnswerResult)) {
            remember({
              key: position,
              box: row.entry.box,
              index: row.entry.index,
              label: row.entry.label,
              dropped,
              at,
              /* "Answer" is what the screen calls the action, so this is what it calls the
               * thing that happened. The condition is what the choice was actually BETWEEN —
               * every candidate row for a finish disagreement carries the same card name — so
               * it is the one word that says which row was pressed. */
              said: `Answered as ${candidate.condition}.`,
            })
          }

          /* Identity preserved when the answered card was never skipped, which is the
           * common case and the hot one: a new array on every answer would invalidate the
           * worklist memo once per card across a whole box for nothing. */
          const answered = new Set(dropped.map((held) => held.key))
          setDeferred((prev) =>
            prev.some((key) => answered.has(key)) ? prev.filter((key) => !answered.has(key)) : prev,
          )
        })
        .catch((err: unknown) => {
          /* Loud, and back where it was. §5.5's rule for a failed capture is that the run
           * stops and says so; the same argument holds here — a card whose answer was
           * refused and which quietly left the queue is a card that will never be looked
           * at again, because nothing re-queues a position the pipeline still considers
           * resolved.
           *
           * EXCEPT FOR THE FOUR CODES THAT MEAN THIS SCREEN IS BEHIND. Two say the card is
           * no longer waiting and two say its rows have been rewritten under the snapshot;
           * STALE_CODES names all four and argues the difference. None of them is a card to
           * put back, and the reason is the same for both pairs: restoring redraws a card
           * whose next press fails identically, which is a loop the operator can only lose.
           * The server's own message says to reload in every one of the four, the panel
           * prints it verbatim beneath the candidate rows, and the panel draws Reload itself.
           *
           * IT WAS TWO CODES UNTIL 2026-08-22 and the missing pair was the expensive half:
           * `already_answered` at least ends with the card gone, while `sku_not_a_candidate`
           * put the card back with the same wrong SKU under the same digit, forever. */
          if (!isStale(err)) restore(dropped)
          /* The card this was about, which is no longer the card on screen: the answer
           * advanced before the write landed, and a stale one is not restored. */
          setRefusal({ failure: describeFailure(err), at: row.entry.label })
        })
        .finally(() => {
          busyRef.current = false
          setBusy(false)
        })
    },
    [rows, putBack, remember],
  )

  /* TAKE ONE ANSWER BACK (D28). The mirror of `answer` above and it holds the same two rules:
   * one round trip at a time in both directions, and the card goes back where it was rather
   * than being re-read.
   *
   * NOTHING IS ADVANCED OR DROPPED OPTIMISTICALLY HERE, WHICH IS THE OPPOSITE OF `answer`. That
   * one advances before the write lands because docs/DESIGN.md says answering advances with no
   * acknowledgement to dismiss, and the cost of being wrong is one card put back. This is the
   * remedy for a wrong write, so it waits for the server: a card drawn back onto the screen on
   * the strength of a reversal that then failed would be the queue disagreeing with the store
   * about a card whose SKU is still written — and the operator would answer it again, on top of
   * an answer that never came off.
   *
   * THE RECEIPT COMES DOWN ONLY WHEN IT HAS NOTHING LEFT TO DO: the reversal worked, or it was
   * refused in one of the four codes that will answer identically forever. See
   * `FINAL_UNDO_CODES`. Anything else — a dead server, a store busy behind a running join — is
   * worth another press, and the window is what ends it. */
  const undo = useCallback(
    (receipt: Receipt) => {
      if (busyRef.current || loadingRef.current) return
      busyRef.current = true
      setBusy(true)
      setRefusal(null)

      /* `.then(ok).catch(fail)` AND NOT `.then(ok, fail)`, for the reason the other three calls
       * in this file give: the two-argument form does not cover its own success handler, so a
       * throw while putting the card back would land as an unhandled rejection with `.finally`
       * clearing `busy` — a screen that looks ready, a receipt still standing, and a card the
       * server has already reopened sitting in neither list. */
      void undoAnswer(receipt.box, receipt.index)
        .then(() => {
          putBack(receipt.dropped, receipt.at)
          setReceipts((held) => held.filter((standing) => standing.key !== receipt.key))
        })
        .catch((err: unknown) => {
          /* The label is the receipt's and not the current card's, the same capture
           * `Refusal` argues for: the card this is about left the screen when it was
           * answered, and by now there is usually a different one on it. */
          setRefusal({ failure: describeFailure(err), at: receipt.label })
          if (isFinalRefusal(err)) {
            setReceipts((held) => held.filter((standing) => standing.key !== receipt.key))
          }
        })
        .finally(() => {
          busyRef.current = false
          setBusy(false)
        })
    },
    [putBack],
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

  /* The read, from three places now — the header button, the key, and the Reload the refusal
   * panel draws for a stale answer. One callback rather than three inline `setReloads`, so
   * that the mutual exclusion the `loading` note argues for has one place to be checked. */
  const reload = useCallback(() => setReloads((n) => n + 1), [])

  /* THE NEXT CARD'S PHOTOGRAPH, FETCHED WHILE THIS ONE IS BEING JUDGED (D28). The worklist
   * already knows which card is next, the photo route is a plain GET, and the browser cache
   * is what makes it free at the moment of the advance — so this is one request the operator
   * never waits on.
   *
   * IT IS THE SECOND HALF OF THE FIX AND NOT THE FIRST. Reserving the frame is what stops the
   * candidate rows moving; this is what stops the photograph arriving blank and popping in.
   * Measured on the Gate B captures at 1440x900 before either landed: advancing drew the next
   * card with a 2px-tall image, the first candidate row at y=373 instead of y=911, and the row
   * came back 538px down the page ~50ms later — under a finger already travelling to a digit.
   * Either fix alone leaves half of that; the frame holds the layout still and the prefetch
   * fills it.
   *
   * ONE CARD AHEAD, NOT THE WHOLE WORKLIST. A queue is hundreds of 4K frames — Gate B's are
   * 2160x3840 — and warming all of them would spend the rig's memory and the server's disk on
   * cards the operator may answer in ten minutes or never reach. The next one is the only
   * request whose result is certainly wanted, because it is the card the current keypress
   * produces.
   *
   * The URL rather than the row as the dependency: `worklist` is rebuilt whenever a skip
   * changes the order, and a string re-fires only when the next card actually changes. */
  const nextPhoto = useMemo(() => {
    const next = worklist[1]
    if (next === undefined) return null
    if (next.entry.box < 1 || next.entry.photo === null) return null
    return photoUrl(next.entry.box, next.entry.index)
  }, [worklist])

  useEffect(() => {
    if (nextPhoto === null) return
    /* Held in a local rather than dropped on the floor: an `Image` whose only reference is
     * the in-flight request is at the browser's discretion, and the point is the cache entry
     * rather than this element. Nothing renders it and nothing reads it back — a failure here
     * is silent by design, because the card it belongs to has its own three absent states and
     * will report the same 404 itself when it is drawn. */
    const warm = new Image()
    warm.src = nextPhoto
    return () => {
      /* Dropping the src cancels a fetch still in flight. A skip can change the next card
       * several times a second, and a queue's worth of abandoned 4K decodes is exactly the
       * kind of idle work Gate B found stalling the capture path. */
      warm.src = ''
    }
  }, [nextPhoto])

  /* The key map, armed once and reading the current card through a closure React rebuilds
   * whenever the card or the handlers change. R reloads, digits pick a candidate, S skips,
   * and C clears the skips for exactly as long as the note offering it is on screen.
   *
   * ARMED WITH NO CARD ON SCREEN, which is new and is the whole reason the `current === null`
   * guard moved inside the handler: reload is the remedy for the state where this screen has
   * no card because the read failed, and it used to be the one state where no key was bound. */
  useEffect(() => {
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

      /* ABOVE THE `current` GUARD, because the state with no card is the state that needs it.
       * The button is disabled for the same window by the two flags checked above. */
      if (key === RELOAD_KEY) {
        event.preventDefault()
        reload()
        return
      }

      /* ALSO ABOVE THE `current` GUARD, and here the reason is sharper than reload's: the
       * answer most likely to want taking back is often the one that emptied the queue, and
       * with no card on screen every branch below this line is dead. It acts on the newest
       * receipt still standing — see `UNDO_KEY`. */
      if (key === UNDO_KEY) {
        const newest = receipts[0]
        if (newest === undefined) return
        event.preventDefault()
        undo(newest)
        return
      }

      if (current === null) return

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
  }, [current, answer, skip, clearSkips, allSkipped, reload, receipts, undo])

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

  /* ONE ELEMENT, DRAWN IN ONE OF TWO PLACES, and the two places are the whole of the layout
   * question this raised. Inside the card it sits immediately below the last candidate row —
   * `RefusalPanel`'s slot, chosen there by measurement as the closest place to the eye that
   * cannot move a row, which is the constraint D28's other half exists to enforce. Nothing
   * above the rows may grow or shrink, so the header, the sentence and the photo frame are all
   * ruled out however much more visible they are.
   *
   * THE SECOND PLACE IS FOR THE CASE THAT MATTERS MOST. Answering the last card empties the
   * worklist and `Card` is not rendered at all — and that is precisely the answer whose undo is
   * most likely to be wanted, because a queue that has just ended is a queue nobody is about to
   * scroll through. So the same element is drawn under the header when there is no card. It
   * moves between parents rather than being duplicated: two call sites for one node, and the
   * node holds no state to lose when React remounts it.
   *
   * REJECTED: A FIXED OVERLAY. It would solve both placements at once and never move anything,
   * and it loses on two counts — it would float over the candidate rows, which are this
   * screen's entire vocabulary, and it needs styles this session does not own. The in-flow slot
   * is already argued for and already styled. */
  const receiptPanel =
    receipts.length === 0 ? null : (
      <Receipts receipts={receipts} onUndo={undo} disabled={busy || loading} />
    )

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
          <button className="review-reload" type="button" onClick={reload} disabled={busy || loading}>
            <span>Reload</span>
            {/* "Every choice shows its key", and this control is a choice the server asks the
                operator to make by name in four of its refusals. */}
            <kbd className="review-key">{RELOAD_KEY_LABEL}</kbd>
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

      {/* A REFUSAL IS DRAWN HERE ONLY WHEN THERE IS NO CARD TO DRAW IT UNDER, which is a
          failed `GET /queues` and nothing else. Every other refusal goes to the bottom of the
          card, beneath the candidate rows — see `RefusalPanel` for the measurement that moved
          it. This branch is what the header keeps: a read that produced no screen has to say
          so where the screen would have been. */}
      {current === null && refusal !== null ? (
        <RefusalPanel refusal={refusal} onReload={reload} disabled={busy || loading} />
      ) : null}

      {rows === null && refusal === null ? (
        <p className="review-note-text">Reading the queues.</p>
      ) : null}

      {rows !== null && worklist.length === 0 ? (
        <p className="review-note-text">Nothing is waiting. Every queued card has been answered.</p>
      ) : null}

      {/* The receipts, when there is no card to draw them inside — see `receiptPanel`.
          BELOW THE TWO LINES ABOVE AND NOT OVER THEM: with the queue emptied, "Nothing is
          waiting" is the state and the receipt is what just happened to get there, so it reads
          in that order. Measured the other way round first, where the screen opened with a
          receipt for a card and explained underneath it that there were no cards. */}
      {current === null ? receiptPanel : null}

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
          refusal={refusal}
          onReload={reload}
          receipts={receiptPanel}
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

  /** The refusal the last write came back with, or null. Drawn at the bottom of this card
   *  rather than above it — see `RefusalPanel`. */
  refusal: Refusal | null
  onReload: () => void

  /** The standing undo receipts, already built, or null when there are none (D28).
   *
   *  A NODE AND NOT A LIST, because they are not this card's — they belong to cards already
   *  answered, and this component is handed a place to put them rather than a reason to know
   *  what they are. The alternative is passing `receipts` and `onUndo` down through a component
   *  whose whole job is one card, which would make `Card` the thing that decides how an undo is
   *  drawn. Where they go and why is at `receiptPanel`. */
  receipts: ReactNode
}

/* WHERE THE EYE ALREADY IS, WHICH IS NOT WHERE THIS PANEL USED TO BE DRAWN.
 *
 * It was rendered between the header and the card. With the photo frame at 60vh that puts a
 * refusal roughly 700px above the candidate rows the operator is looking at — off-screen at
 * 1440x900, measured — so a refused answer was invisible at the moment it happened. The card
 * had meanwhile been restored and was the next keypress's target, which is the worst possible
 * pairing: an unseen refusal and a re-armed digit.
 *
 * ABOVE THE CANDIDATE ROWS WAS THE OBVIOUS FIX AND IT IS THE ONE THING THIS PANEL MAY NOT DO.
 * Anything that appears between the sentence and the rows pushes every row down by its own
 * height, which is precisely the movement D28 sent this session to remove. So it goes
 * immediately BELOW the last candidate row: the closest place to the eye that cannot move a
 * row, and the same reasoning `Facts` was moved to the bottom for.
 *
 * IT DRAWS ITS OWN RELOAD FOR A STALE REFUSAL, and only for those. The four codes in
 * STALE_CODES all end their message by telling the operator to reload, and none of them
 * restores the card — so the remedy is not the digit under his hand, and the header's button
 * is a screen away. Every other refusal has already put the card back, where the remedy is to
 * press the same digit again and the panel would be offering a detour.
 *
 * Not filled, like everything else on this screen. A refusal is not the one thing to do.
 */
function RefusalPanel({
  refusal,
  onReload,
  disabled,
}: {
  refusal: Refusal
  onReload: () => void
  disabled: boolean
}) {
  return (
    /* `role="alert"` because this panel now appears below the fold as often as not, and the
       one thing it may not be is silent. It is owner-side, so a screen reader here is a
       keyboard user's, not the Fulfiller's. */
    <div className="review-note" role="alert">
      <p className="review-note-text">{refusal.failure.message}</p>
      {/* The code beneath the sentence and never the sentence again — a greppable token,
          which is the whole of what the small line is for. The position rides with it because
          the card this was about is usually no longer the card on screen: the answer advanced
          before the write landed, and a stale one is never restored. */}
      <p className="review-machine">
        {refusal.failure.code}
        {refusal.at === null ? '' : ` · ${refusal.at}`}
      </p>
      {STALE_CODES.has(refusal.failure.code) ? (
        <button className="review-action" type="button" onClick={onReload} disabled={disabled}>
          <span>Reload</span>
          <kbd className="review-key">{RELOAD_KEY_LABEL}</kbd>
        </button>
      ) : null}
    </div>
  )
}

/* THE UNDO RECEIPTS — D28's twenty seconds, drawn.
 *
 * ONE PANEL PER ANSWER, newest at the top, each with its own deadline. See `Receipt` for why
 * this is a list and `UNDO_WINDOW_MS` for what the clock costs.
 *
 * IT REUSES `review-note`, WHICH IS `RefusalPanel`'s SHELL. Not a shortcut: this is the same
 * kind of thing — a sentence, a machine line, and one control — sitting in the same slot, and a
 * second panel style for it would be a second set of paddings and hairlines to keep in step
 * with the first. The stylesheet is untouched by this change as a result.
 *
 * NOT FILLED, like everything else on this screen. `Card` has the rule in full: solid accent is
 * reserved for a screen with exactly one thing to do, and this screen's whole business is a
 * choice between rows. An undo is not that one thing either — it is the way back from a choice
 * already made, which is what the Fulfiller's mark-sold undo is too, and that one is not filled
 * on its own view.
 *
 * `role="status"` AND NOT `role="alert"`. The refusal panel is an alert because it reports a
 * failure the operator may not be looking at; this reports a success and offers an option, and
 * an assertive interruption on every single answer would make the screen unusable with a screen
 * reader at exactly the pace this screen is built for.
 */
function Receipts({
  receipts,
  onUndo,
  disabled,
}: {
  receipts: readonly Receipt[]
  onUndo: (receipt: Receipt) => void
  disabled: boolean
}) {
  return (
    <>
      {receipts.map((receipt, at) => (
        <div className="review-note" role="status" key={receipt.key}>
          <p className="review-note-text">{receipt.said}</p>
          {/* The position, in the utility face, because the card this is about is no longer the
              card on screen — the same capture `RefusalPanel` makes and for the same reason.
              With several receipts standing this line is the only thing telling them apart, so
              it is the identifier rather than decoration. */}
          <p className="review-machine">{receipt.label}</p>
          <button
            className="review-action"
            type="button"
            onClick={() => onUndo(receipt)}
            disabled={disabled}
          >
            <span>Undo</span>
            {at === 0 ? (
              <kbd className="review-key">{UNDO_KEY_LABEL}</kbd>
            ) : (
              /* A DASH RATHER THAN AN EMPTY BOX, the same treatment a tenth candidate row gets
                 and the same reasoning: the key acts on the newest receipt, so an older one is
                 answered with the mouse, and a blank where a chip belongs reads as a chip that
                 failed to render rather than as a row that never had one. */
              <span className="review-key-blank" aria-hidden="true" title="No key. Click this one.">
                –
              </span>
            )}
          </button>
        </div>
      ))}
    </>
  )
}

/* Photo first, then the finding, then the rows. Single column, so the same layout works on a
 * laptop and a phone — docs/DESIGN.md rejects a left/right split by name. */
function Card({
  row,
  activity,
  photoAbsent,
  onPhotoAbsent,
  onChoose,
  onSkip,
  refusal,
  onReload,
  receipts,
}: CardProps) {
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
                  /* A DASH RATHER THAN AN EMPTY BOX, AND THE BEHAVIOUR IS UNCHANGED. Rows
                     past the ninth have no key — docs/DESIGN.md records that deviation and
                     its reasoning, and this is not a reopening of it. What was wrong was
                     silence: the blank held the column and said nothing, so a row with no key
                     looked exactly like a row whose key had failed to render, on a screen
                     where the operator's entire vocabulary is digits. The dash says the row
                     is answered with the mouse, which is what the design decided.
                     `aria-hidden`, because the glyph is a mark for the eye and a screen
                     reader gets the row's name, condition and price either way. */
                  <span
                    className="review-key-blank"
                    aria-hidden="true"
                    title="No key. Click this row."
                  >
                    –
                  </span>
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

      {/* Beneath the rows, never above them. `RefusalPanel` holds the measurement and the
          rule: this is the closest place to the eye that cannot move a candidate row. */}
      {refusal === null ? null : (
        <RefusalPanel refusal={refusal} onReload={onReload} disabled={busy} />
      )}

      {/* The undo receipts, in the same slot and for the same reason (D28). Under the refusal
          rather than over it: a refusal is about the press just made and a receipt is about a
          card already gone, so the newer thing is nearer the rows. */}
      {receipts}

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
 * gone from disk. Each says which, and prints what was asked for.
 *
 * ALL FOUR STATES ARE DRAWN INSIDE ONE RESERVED FRAME (D28), and that is the whole of the
 * layout fix on this side of the wire. `.review-frame` holds the same height whether the
 * image has loaded, is still loading, failed, or never existed — so the 538px round trip
 * measured on the Gate B captures cannot happen, and the candidate rows below sit at one y
 * for every card that carries the same reason. What still moves them is the sentence, by one
 * 26px line where a reason has two; the number, the trade and why it is not reserved either
 * are all in ReviewQueue.css beside the cap.
 *
 * A CARD WITH NO PHOTOGRAPH RESERVES THE SPACE TOO, which looks like waste and is the point.
 * The alternative is a frame that collapses for exactly the entries the pipeline is least
 * sure about — `no_position` and `identification_failed` have no photo by construction — so
 * a mixed queue would move the rows on precisely the cards that most deserve a careful
 * answer. A reserved box is only worth having if nothing is exempt from it. */
function Photo(props: { row: Row; absent: boolean; onAbsent: () => void }) {
  /* THE FRAME CARRIES NO BORDER, GROUND OR RADIUS OF ITS OWN. The border belongs to the
     photograph, which still hugs its own edges exactly as it did before this wrapper existed
     — docs/DESIGN.md records the alternative by name: a bordered box with a correct
     photograph inside it and an equal area of empty surface beside it, which "looks like a
     bug". A frame that reserves space and draws nothing is invisible when the photograph
     fills it and invisible when it does not. */
  return (
    <div className="review-frame">
      <PhotoContent {...props} />
    </div>
  )
}

function PhotoContent({
  row,
  absent,
  onAbsent,
}: {
  row: Row
  absent: boolean
  onAbsent: () => void
}) {
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
  /* WHAT THIS QUEUE IS MADE OF, in the pipeline's own strings and in descending count. Gate B
   * is the argument: 16 of 53 cards queued and every one of them was
   * `metadata_detection_disagreement` — systematic sheen under the rig's lighting rather than
   * sixteen individual cards, which is a fact about the RIG and was worked out afterwards from
   * the run report rather than seen on the screen that displayed all sixteen. A queue that is
   * one reason repeated wants a different response from one with a spread in it, and D3 draws
   * exactly that distinction: a run full of contradictions means a stack is misfiled, while
   * disagreements scattered across a run mean individual cards are mis-sorted.
   *
   * ON THIS SECTION'S OWN HEADING AND NOT AT THE TOP OF THE SCREEN, which is where it was
   * asked for. Every pixel above the card pushes the candidate rows further below the fold —
   * they already start at y=911 of 900 at 1440x900 — and this list is where a shape is read
   * against the rows that make it up. Nothing above the photograph moved to make room for it.
   */
  const shape = useMemo(() => {
    const counts = new Map<string, number>()
    for (const row of rows) counts.set(row.entry.reason, (counts.get(row.entry.reason) ?? 0) + 1)
    return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  }, [rows])

  return (
    <section className="review-waiting">
      <h2 className="review-waiting-title">
        <span>Waiting</span>
        {/* The machine string with its count, biggest group first — `16
            metadata_detection_disagreement` in Gate B's case. The reason code and not its
            human label: this line is read against the worklist rows below it, which carry the
            same string, and against the run report, which carries it again. */}
        {shape.map(([reason, n]) => (
          <span className="review-waiting-shape" key={reason}>
            {n} {reason}
          </span>
        ))}
      </h2>
      <ul className="review-waiting-list">
        {rows.map((row) => (
          <li
            key={row.key}
            className="review-row"
            data-band={bandOf(row.entry.market)}
            data-parked={row.queue === 'parked' ? 'true' : undefined}
            aria-current={row.key === currentKey ? 'true' : undefined}
          >
            {/* `title` because this cell ellipsises: a long name — `Wally's Compassion -
                132/132` is a real one from Gate B — is cut without a way to read the rest, and
                this list is not pressable, so hover is the only affordance it can have. */}
            <span className="review-row-name" title={text(row.entry.read.name) ?? undefined}>
              {text(row.entry.read.name) ?? 'not identified'}
            </span>
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
