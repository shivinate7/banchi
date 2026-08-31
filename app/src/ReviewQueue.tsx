import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { PositionLabel } from './PositionLabel'
import { isEditableTarget } from './keys'
import type {
  AnswerResult,
  CandidateRow,
  CatalogLookup,
  QueueEntryWire,
  QueueName,
  QueueRead,
  QueueSnapshot,
  RetireReason,
  StandDownReason,
} from './types'
import type { Failure } from './server'
import {
  ServerError,
  answerReview,
  answerReviewGroup,
  describeFailure,
  getQueues,
  photoUrl,
  retireCard,
  reviewCatalog,
  standDown,
  undoAnswer,
  undoRetire,
  undoStandDown,
} from './server'
import './ReviewQueue.css'
import { reasonLabel } from './reasons'
import { collectorNumber as sharedCollectorNumber } from './cardNumber'

/* The review queue — build-order step 7b, specified in docs/DESIGN.md's own section.
 *
 * "The hardest screen in the product and the one the owner spends hours in, so its shape is
 * part of the design and not left to step 7." Every structural choice below is that
 * section's, not this file's: one card at a time, photo first, the choices BESIDE the
 * photograph above 900px and beneath it below (the split that section forbade until
 * 2026-08-24, reversed there with its measurement); the sentence before the candidates; the price-driven type scale; accent outlined and never filled where
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
 * THREE ROUTES, ONE OF THEM TWO-WAY, in `server/capture_server.py`:
 *
 *   GET  /queues                      both standing queues, already in worked order
 *   POST /review/<box>/<index>/answer one candidate row, chosen  (D4) — or `{"undo": true}`,
 *                                     which takes that answer back and puts the card in the
 *                                     queue again (D28)
 *   POST /review/group-answer         a homogeneous group answered in one write — the one
 *                                     narrow exception to one-card-at-a-time, ratified in
 *                                     docs/DECISIONS.md ("A homogeneous queue may be
 *                                     answered as a group") on Gate B's sixteen-of-one-
 *                                     reason evidence. Grouping and filtering are ALWAYS
 *                                     available (the reason chips on the Waiting heading);
 *                                     the write is offered only when every card in the
 *                                     filtered worklist shares one reason and offers one
 *                                     row of one condition — `groupOffer` holds the
 *                                     reading, the route re-enforces it, and the state
 *                                     that draws it shows every photograph first.
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

/** D3 rung 1's finish claim as its members, or null for no claim.
 *
 *  TWO SHAPES, PERMANENTLY. The claim became a SET on 2026-08-23 and a bare string reads as
 *  one member — there is no migration, and a `review.json` written before that date is
 *  still a file this screen opens.
 *
 *  IT CANNOT BE `text()`, AND THAT IS THE WHOLE REASON IT EXISTS. `text()` fails CLOSED on
 *  anything that is not a string: it returns null, so a two-member claim would render as
 *  "no claim" and drop out of the sentence entirely — no crash, no console warning, nothing
 *  red in `tsc`, `lint` or Playwright, while the operator was asked to judge a card against
 *  a claim they never made. The union on `QueueRead.metadata_finish` is what turns that into
 *  a compile error; this is what answers it.
 *
 *  Members are returned rather than a joined string because the two call sites join
 *  differently on purpose: the SENTENCE reads " or " because it is prose a human reads, and
 *  the fact row uses the app's " · " because it is metadata. One source, two renderings —
 *  the strings themselves are the pipeline's own either way (D22). */
function claimMembers(field: string | string[] | null | undefined): string[] | null {
  const members = (typeof field === 'string' ? [field] : Array.isArray(field) ? field : [])
    .filter((member): member is string => typeof member === 'string')
    .map((member) => member.trim())
    .filter((member) => member !== '')
  return members.length === 0 ? null : members
}

/* THE COMPOSITION MOVED TO `cardNumber.ts` AND THE RENDERING DID NOT CHANGE (D67). This copy
 * was the correct one of the three — it already folded a blank on both halves — and it is gone
 * for the reason the other two are: one composer, so the next screen cannot write a fourth.
 *
 * WHAT THIS SCREEN DELIBERATELY DOES NOT GET IS THE SET-CODE FOLD. `QueueRead` carries no
 * `number_display`, so this composes the raw pair and shows exactly what the model returned —
 * `UNL / 120/219` and all. D55 was FOUND by the owner reading that string here three times in
 * one afternoon; a queue that quietly tidied it would have hidden its own evidence. The
 * inventory screens draw the folded form because they are naming a card that is already in a
 * box; this one is judging the read that put it there.
 */
function collectorNumber(read: QueueRead): string | null {
  return sharedCollectorNumber({ number: read.number, printed_total: read.printed_total })
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
  const toggle = claimMembers(entry.read.metadata_finish)?.join(' or ') ?? null
  const detected = text(entry.read.detected_finish)
  const hint = text(entry.read.set_hint)
  const name = text(entry.read.name)
  const only = soleCondition(entry.candidates)

  switch (entry.reason) {
    case 'no_catalog_row':
      return number === null
        ? [say('The export has no row for this card.')]
        : [say('The export has no row for '), value(number), say('.')]

    /* D35. Both halves of the sentence are load-bearing and neither may be dropped: what was
     * NOT read, and what was matched instead. The operator is being asked to confirm an
     * identity that was established without its primary key, so the sentence has to say that
     * outright — a card whose number is simply absent from the photograph and one whose
     * number was misread into a Pokedex number look identical here otherwise. */
    case 'number_unread_name_matched': {
      const head: Segment[] =
        number === null
          ? [say('No collector number could be read from this photograph. ')]
          : [say('The number read as '), value(number), say(', which is in no row. ')]
      const matched: Segment[] =
        only === null
          ? [say(' matched one row in this set by name.')]
          : [say(' matched one '), claim(only), say(' row in this set by name.')]
      return name === null
        ? [...head, say('The name matched one row in this set.')]
        : [...head, value(name), ...matched]
    }

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

    /* D23's job (a), and it had no sentence here from the day the reason shipped — the
     * fallback below drew "a reason this screen has no sentence for" over the one entry in
     * the owner's whole store, which is where D75 found it.
     *
     * WHAT IT HAS TO SAY IS THAT THE ROWS MAY BE ANOTHER CARD, and nothing else on screen
     * says it. Every other reason on this list is a question about WHICH row; this one is
     * the only reason the pipeline emits that can mean the rows themselves are wrong, which
     * `pipeline/variant.py` states outright where it fires: it is the reason that catches a
     * misread number, `051/197` read for `031/197`, "a CONFIDENT answer no confidence
     * threshold fires on". An operator who reads these rows as a shortlist for this card has
     * been misled by the screen rather than by the pipeline.
     *
     * IT DOES NOT QUOTE THE CLAIM, because it cannot. `QueueEntry` records the read and the
     * candidates and not `rarity_claim` — that lives on `master.Card` — so naming the
     * rarities here would need a schema change, and "the rarities claimed at capture" is
     * true, checkable against the capture screen, and does not invent a value. */
    case 'rarity_claim_mismatch': {
      const head: Segment[] =
        number === null
          ? [say('The rarities claimed at capture match none of the rows below. ')]
          : [
              say('The rarities claimed at capture match none of the rows '),
              value(number),
              say(' found. '),
            ]
      return [
        ...head,
        say(
          'That is what a misread number looks like when the misreading is confident: the number found real rows, but they may belong to a different card entirely. Check them against the photograph before answering.',
        ),
      ]
    }

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

/* TEN ANSWERS DEEP, AND NO CLOCK AT ALL. This was twenty seconds, copied from
 * `Fulfillment.tsx:UNDO_WINDOW_MS` because D28 asks for "the shape the product already ships".
 * The copy was right about the shape and wrong about the screen, and the difference is pace.
 *
 * Mark-sold happens with the card in his hand: he pulls it, presses once, and knows
 * immediately whether it was the right one. Twenty seconds is generous there because the
 * feedback is physical and instant. Review runs at two to six seconds a card for an hour, and
 * the mistake is noticed the way mistakes on a fast loop always are — three cards later, when
 * something about the last one nags. A twenty-second window is about four cards wide, so it
 * expires at almost exactly the moment it becomes useful; and it reached only the newest
 * answer anyway, so noticing at N+3 meant it was never reachable at all.
 *
 * So the bound moves from time to COUNT: the last ten answers stay reversible until ten more
 * push them out. Prodigy, the reference tool for annotation throughput, runs a ten-deep
 * history with no expiry for the same reason. `Fulfillment.tsx` keeps its twenty seconds —
 * different screen, different pace, and D28's shape rule was never a rule about the number.
 *
 * THIS IS A CHANGE OF BOUND, NOT OF RULE. `store/queues.py:Queue.upsert` still refuses to
 * re-queue a position a human has cleared, so an answer still outlives its question for
 * everything outside the ten; this is the hole D28 punched through that, made a useful size.
 *
 * WHAT IT COSTS, RECORDED RATHER THAN DISCOVERED. Both were true of the clock too:
 *
 *   it does not survive a reload   The receipts live in component state, so a refresh, a route
 *                                  change or a crash takes every standing undo with it. The
 *                                  answer is written and the card stays answered; what is lost
 *                                  is the way back. The trigger for revisiting is the first
 *                                  answer actually lost that way, and the fix would be reading
 *                                  the `answered` history line back rather than holding more
 *                                  here.
 *   the other device knows nothing A browser that never saw the answer never draws its undo
 *                                  (D13: two devices, one store, no session between them). The
 *                                  route would accept the reversal from either; only this
 *                                  screen decides to offer it.
 */
const UNDO_DEPTH = 10

/* Enter the group state: the whole eligible worklist drawn as photographs over one confirm
 * (docs/DECISIONS.md, "A homogeneous queue may be answered as a group" — the entry that
 * reopens D4's one-card-at-a-time, narrowly). Offered only while `groupOffer` says the
 * worklist qualifies, so the key is bound for exactly as long as the control is drawn —
 * the same rule CLEAR_KEY states for the skip note.
 *
 * INSIDE THE STATE THE KEYS ARE Enter AND Escape, NOT A DIGIT, and that is deliberate on
 * both sides. The digits are the one-card answering vocabulary and a group press must not
 * sit on a key the finger already drums; Enter is free precisely because D28 declined it as
 * a per-card confirm, and here it confirms a state the operator chose to enter rather than
 * doubling a keystroke. Escape leaves without writing, which is what Escape means.
 */
/* D37. `X` for "close this out", and it opens a panel rather than writing — every choice
 * behind it needs a reason, so a single keystroke could not carry one honestly. The panel
 * owns the keyboard while it is up, exactly as the group offer does, which is what makes it
 * safe to key the choices on digits that mean candidates everywhere else. */
const CLOSE_KEY = 'x'
const CLOSE_KEY_LABEL = 'X'

/* D75. `L` for "look it up", and it is the letter the paragraph above `SKIP_KEY` reserved and
 * then handed back: an early draft bound it to "Leave unlisted" for the zero-candidate card,
 * the route refused that idea, and the letter has been free ever since.
 *
 * IT OPENS A LIST; IT NEVER WRITES. Pressing it swaps the pipeline's rows for the export's,
 * and the digits then mean the export's rows — which is why it SWAPS rather than appends.
 * Two lists of candidate rows on one screen, both answered on digits, is the one shape this
 * screen must never take; D46's zero-candidate arm avoided it by arithmetic, and now that
 * both lists can exist for one card it has to be avoided on purpose. Escape comes back.
 *
 * NOT AUTOMATIC, WHICH IS D46'S SECOND ARGUMENT KEPT RATHER THAN OVERTURNED. That entry
 * refused to fetch a catalog beside a good list of rows, because "a second, looser list
 * beside a good one is how a screen teaches you to stop reading the first". True, and it is
 * an argument about what is drawn UNASKED. A list the operator pressed a key to see is one
 * they have already decided the first list failed to answer. */
const LOOKUP_KEY = 'l'
const LOOKUP_KEY_LABEL = 'L'

/** What pressing a row in the close panel does. */
type CloseChoice =
  | { kind: 'stand_down'; reason: StandDownReason }
  | { kind: 'retire'; reason: RetireReason }

/* THE PANEL IS THE PLACE THE DIFFERENCE IS TAUGHT, and it is the reason these two live on one
 * control instead of two. The owner's question was "why can't I delete a card from here, and
 * why can't I stand down on the flag" — and the honest answer is that those are three
 * different acts with three different costs, which no button label can convey on its own.
 *
 * DELETE IS DELIBERATELY ABSENT. `POST /inventory/<box>/<index>/remove` exists and works, but
 * it slides every card behind it down one slot — so pressing it from a worklist would
 * renumber the very positions that worklist is drawn from, and it is a hard delete with no
 * undo at all. It stays on the Inventory screen, where the box you are renumbering is the
 * thing on screen. Retire reaches the same practical end here (the card stops being active)
 * while moving nothing and staying reversible. */
const CLOSE_CHOICES: {
  choice: CloseChoice
  label: string
  machine: string
  note: string
}[] = [
  {
    choice: { kind: 'stand_down', reason: 'wasted_position' },
    label: 'Wasted position',
    machine: 'wasted_position',
    note: 'The slot holds nothing worth listing — a double feed, a divider, a blank.',
  },
  {
    choice: { kind: 'stand_down', reason: 'cannot_settle' },
    label: 'Cannot settle it',
    machine: 'cannot_settle',
    note: 'The photograph will not decide this one, and it is not worth re-shooting.',
  },
  {
    choice: { kind: 'stand_down', reason: 'not_listing' },
    label: 'Not listing it',
    machine: 'not_listing',
    note: 'A real card you have decided not to list. It keeps its slot either way.',
  },
  {
    choice: { kind: 'retire', reason: 'pulled' },
    label: 'Pulled',
    machine: 'pulled',
    note: 'Taken out of the box by hand.',
  },
  {
    choice: { kind: 'retire', reason: 'damaged' },
    label: 'Damaged',
    machine: 'damaged',
    note: 'Not sellable at the condition this pipeline hardcodes.',
  },
  {
    choice: { kind: 'retire', reason: 'lost' },
    label: 'Lost',
    machine: 'lost',
    note: 'Gone, and not sold.',
  },
  {
    choice: { kind: 'retire', reason: 'given_away',
    },
    label: 'Given away',
    machine: 'given_away',
    note: 'It left without a sale.',
  },
]

const GROUP_KEY = 'g'
const GROUP_KEY_LABEL = 'G'


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
/* THE GROUP ROUTE'S TWO REFUSALS ARE IN THE SET TOO, and they arrive only from
 * `answerReviewGroup` — the single route never speaks them. Both mean the same thing the
 * four above mean, at group scale: `group_entry_refused` is the store having moved past the
 * screen that drew the group, with every failing position named by its own code inside the
 * message; `group_not_uniform` is a group the server will not accept as one, which a screen
 * computing eligibility from live rows should never send and a reload re-derives either
 * way. Neither restores anything, because the group write drops nothing until the server
 * says it landed — the set's no-restore half is vacuous for them and its draw-the-Reload
 * half is the point. */
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
/** One position an undo has to reach, with the label a refusal about it is drawn under. */
type UndoTarget = {
  box: number
  index: number
  /** `Row.entry.position` — the store's own key. */
  position: string
  /** The server's own rendered label. Never composed here (D10). */
  label: string
}

type Receipt = {
  /** The single answer's position, or the group's positions joined — either way, a key no
   *  OTHER standing receipt can share, because every position in it is cleared server-side
   *  for as long as the receipt stands. A second answer at one position replaces its receipt
   *  rather than stacking one on it, which cannot happen today — the entry is cleared in
   *  between — and is the same rule `Fulfillment.tsx` states for a second sale of one
   *  position. */
  key: string

  /** ONE FOR A SINGLE ANSWER, THE WHOLE GROUP FOR A GROUP WRITE, and the undo walks them in
   *  order. One list rather than two receipt kinds: a single answer is a group of one to the
   *  reversal, and a second code path is a second thing to keep true. */
  targets: UndoTarget[]

  /** The machine line: the single target's own label, or `16 cards · <reason>` for a group —
   *  with several receipts standing this line is what tells them apart. */
  label: string

  /** Every row this answer dropped — both queue twins per position, the whole worklist for a
   *  group — and the index in `rows` the first was spliced out of. */
  dropped: Row[]
  at: number

  /** The sentence. "Answer" is the action, so the receipt says "Answered", which is
   *  docs/DESIGN.md's rule that an action keeps its name through the whole flow. */
  said: string

  /** HOW TO TAKE THIS ONE BACK, carried on the receipt rather than assumed by `undo` (D37).
   *  Three writes now end up here — an answer, a stand-down and a retirement — and each has
   *  its own reversal route. `undo` used to call `undoAnswer` unconditionally, which was
   *  right while an answer was the only thing that produced a receipt and becomes a silent
   *  cross-wiring the moment it is not: reversing a retirement through the answer route
   *  refuses `not_answered`, and the operator reads a true refusal about the wrong question.
   *
   *  The whole receipt shape is otherwise unchanged, which is the point — `U` acts on the
   *  newest receipt without caring what made it, and the walk, the partial-reversal report
   *  and the final-refusal rule are one code path for all three. */
  reverse: (box: number, index: number) => Promise<unknown>
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

  /* WORK ONE REASON AT A TIME (docs/DECISIONS.md, "A homogeneous queue may be answered as a
   * group": grouping and filtering, ALWAYS — the filter is unconditional even when the group
   * write below never qualifies). Null is every reason, which is the screen as it has always
   * been. The chips on the Waiting heading set it, because that heading's shape line is
   * where a queue's composition is read — Gate B's sixteen-of-one-reason was a fact about
   * the RIG, and working one reason as a block is how such a fact is worked.
   *
   * A LENS, NOT STATE ABOUT ROWS: nothing is written, a filtered-out card is still open in
   * its file and still counted by the run report, and it survives a Reload — the fresh
   * snapshot is read through the same lens, unlike the skips, which a reload forgets. */
  const [reasonFilter, setReasonFilter] = useState<string | null>(null)

  /* THE GROUP STATE — the one narrow exception to one-card-at-a-time, entered on purpose
   * and left the same way. While true (and while the worklist still qualifies), the screen
   * draws every photograph the group write would answer for over ONE confirm control,
   * because the ruling's own condition is that "a group write still shows the photographs
   * it is about to answer for". Not persisted anywhere, exactly like a skip: reload the
   * page and the queue is one card at a time again. */
  const [grouping, setGrouping] = useState(false)

  /* D37's close panel — `X` raises it for the card on screen. Not persisted, for the same
   * reason `grouping` is not: a panel that writes on a digit must be re-raised deliberately,
   * never restored by a page load into a state where the next keystroke closes a card. */
  const [closing, setClosing] = useState(false)

  /* D46 — what this card COULD be, for an entry the pipeline offered nothing for.
   *
   * IN THE CONTAINER RATHER THAN IN `Card`, for `closing`'s reason one line up: it is fetched
   * per card and must be cleared when the card changes, and state that lives in the component
   * being replaced cannot be cleared by the thing replacing it.
   *
   * `lookup` is null until the fetch answers, which is what tells the panel to say it is
   * looking rather than to draw an empty result — those are different sentences and only one
   * of them means "this card matches nothing". */
  const [lookup, setLookup] = useState<CatalogLookup | null>(null)
  const [lookupFailed, setLookupFailed] = useState<string | null>(null)
  const [typed, setTyped] = useState('')

  /* D75 — the row key the operator asked to see the export for, because none of the rows the
   * pipeline offered is the card in the photograph.
   *
   * THE KEY RATHER THAN A BOOLEAN, which is `photoAbsent`'s reason two states down and is
   * load-bearing here rather than stylistic. A boolean would have to be cleared when the
   * queue advances, and there is no ordering of that reset against the fetch effect below
   * that does not either carry the export onto the next card for a frame — unasked, which is
   * the one thing D46 argued against — or fire a lookup for a card nobody asked about. A key
   * that simply stops matching `current.key` is false the instant the card changes, with no
   * effect to run and nothing to sequence. */
  const [lookingAt, setLookingAt] = useState<string | null>(null)

  /* The key whose photo 404'd rather than a boolean, for PullPreview.tsx's reason: an
   * `onError` for the previous card can land after the queue has advanced, and a boolean
   * would blame the wrong card for a missing file. */
  const [photoAbsent, setPhotoAbsent] = useState<string | null>(null)

  /* The last ten answers (D28), newest first, each still reversible. See `Receipt` for why
   * this is a list, and `UNDO_DEPTH` for why the bound is a count rather than a clock.
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
  const { everyone, worklist, allSkipped } = useMemo(() => {
    if (rows === null) return { everyone: [] as Row[], worklist: [] as Row[], allSkipped: false }

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

    /* `everyone` IS THE WHOLE QUEUE AND `worklist` IS THE LENS OVER IT. The Waiting list
     * draws everyone — a filtered-out card is still waiting, and a list that hid it would
     * make the shape chips lie about a queue the count line still sums — while the card
     * being worked, the keys and the group write all read the filtered view. The filter
     * applies AFTER the skip partition, so a skip keeps its meaning across a filter change
     * rather than being re-derived inside each lens. */
    const everyone = [...held, ...pushed]
    const match = (row: Row) => reasonFilter === null || row.entry.reason === reasonFilter
    const heldIn = held.filter(match)
    const pushedIn = pushed.filter(match)

    return {
      everyone,
      worklist: [...heldIn, ...pushedIn],
      allSkipped: heldIn.length === 0 && pushedIn.length > 0,
    }
  }, [rows, deferred, reasonFilter])

  const current = worklist[0] ?? null

  /* THE GROUP OFFER, RE-DERIVED FROM LIVE ROWS ON EVERY CHANGE AND NEVER SNAPSHOTTED. The
   * ruling's two conditions, read honestly: every card in the (filtered) worklist shares one
   * reason code, and every one offers THE SAME SINGLE CANDIDATE — which this screen reads as
   * exactly one row per entry, of one condition across the group, each row the entry's own.
   * It cannot mean one shared SKU: sixteen different cards are sixteen different catalog
   * rows, and answering card A with card B's SKU is not a reading of the entry, it is data
   * corruption wearing one. What is identical across the sixteen taps is the SHAPE of each
   * answer — same question, one possible reply each, every reply of one kind — and the
   * server enforces the same three checks in `group_not_uniform`, so this memo is a
   * convenience and never the guard.
   *
   * TWO CARDS MINIMUM. A "group" of one is the single flow with extra steps, and offering a
   * second way to answer one card is two controls for one write.
   *
   * NO FILTER REQUIRED WHEN NONE IS NEEDED: a queue that is one reason end to end — Gate
   * B's, sixteen times over — qualifies unfiltered, and demanding a filter tap first would
   * be a ritual. The filter is for carving a qualifying group out of a mixed queue. */
  const groupOffer = useMemo((): { rows: Row[]; reason: string; condition: string } | null => {
    if (worklist.length < 2) return null
    const first = worklist[0]
    if (first === undefined) return null
    const reason = first.entry.reason
    const conditions = new Set<string>()
    for (const row of worklist) {
      if (row.entry.reason !== reason) return null
      const only = row.entry.candidates[0]
      if (only === undefined || row.entry.candidates.length !== 1) return null
      conditions.add(only.condition)
    }
    const [condition] = [...conditions]
    if (condition === undefined || conditions.size !== 1) return null
    return { rows: worklist, reason, condition }
  }, [worklist])

  /* The state outlives its offer otherwise: answer the group, reload into a queue that no
   * longer qualifies, and `grouping` would be pointing at a screen with nothing to draw. */
  useEffect(() => {
    if (grouping && groupOffer === null) setGrouping(false)
  }, [grouping, groupOffer])

  /* THE PANEL NEVER SURVIVES THE CARD IT WAS RAISED FOR. Without this, answering or skipping
   * with the panel up would leave it standing over the NEXT card and the next digit would
   * close that one instead — a write against a card the operator never chose, which is the
   * whole hazard of keying choices on digits that mean something else everywhere on this
   * screen. */
  const currentKey = current?.key ?? null
  useEffect(() => {
    setClosing(false)
  }, [currentKey])

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
  const remember = useCallback((receipt: Receipt) => {
    setReceipts((held) =>
      [receipt, ...held.filter((standing) => standing.key !== receipt.key)].slice(0, UNDO_DEPTH),
    )
  }, [])

  /* CLOSE A CARD WITHOUT ANSWERING IT — D37's stand-down, and D26's retirement reached from
   * the screen the card is actually on.
   *
   * ONE CALLBACK FOR BOTH, because from this screen's point of view they are the same
   * gesture with different consequences: the card leaves the worklist, a receipt stands for
   * twenty seconds, and `U` takes it back. What differs is the route, which the receipt now
   * carries (`Receipt.reverse`), and what it means — which is the panel's job to say, not
   * this function's.
   *
   * DELIBERATELY SIMPLER THAN `answer`, and the missing parts are missing for a reason.
   * There is no candidate to validate, because nothing is being identified. There is no
   * `clearedQueues` read, because neither route reports per-queue clearing and both clear
   * everything they find or refuse outright. And there is no `restores_to` gate: a
   * stand-down writes nothing downstream so it is always reversible, and a retirement's own
   * route answers `restores_to` which this checks before standing a receipt up.
   *
   * IT DOES NOT ADVANCE OPTIMISTICALLY THE WAY AN ANSWER DOES, and that is the one place it
   * departs from docs/DESIGN.md's no-acknowledgement rule on purpose. An answer is the
   * common case and pays for its optimism; closing a card is rare, deliberate, and the
   * operator has just read a panel to get here — so the row is dropped only once the server
   * has confirmed, and a refusal never has to put a card back under a finger already moving. */
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

      const call =
        how.kind === 'stand_down'
          ? standDown(row.entry.box, row.entry.index, how.reason)
          : retireCard(row.entry.box, row.entry.index, how.reason)

      void call
        .then((result: unknown) => {
          setRows((prev) =>
            prev === null ? prev : prev.filter((held) => held.entry.position !== position),
          )
          /* A RETIREMENT'S UNDO IS THE SERVER'S CALL AND A STAND-DOWN'S IS NOT, which is the
           * one asymmetry worth carrying rather than flattening. `RetireResult.restores_to`
           * is null when the log cannot say what state the copy was in — the same contract
           * `markSold` states — and a control whose only outcome is a refusal is the defect
           * docs/DESIGN.md records as having shipped twice. A stand-down has no prior state
           * to restore, so nothing can withhold it. */
          const reversible =
            how.kind === 'stand_down' ||
            (result as { restores_to?: unknown } | null)?.restores_to != null
          if (!reversible) return
          remember({
            key: position,
            reverse: how.kind === 'stand_down' ? undoStandDown : undoRetire,
            targets: [
              {
                box: row.entry.box,
                index: row.entry.index,
                position,
                label: row.entry.label,
              },
            ],
            label: row.entry.label,
            dropped,
            at,
            /* docs/DESIGN.md's copy rule: the action keeps its name through the flow, so the
             * receipt says back exactly what the panel offered. */
            said: how.kind === 'stand_down' ? 'Stood down' : 'Retired',
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
    [rows, remember],
  )

  const answer = useCallback(
    (row: Row, candidate: CandidateRow, fromCatalog = false) => {
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
        // D46. Only ever set for a row that came out of the catalog lookup, which the server
        // accepts only for an entry with no candidates of its own — and even then it re-reads
        // the row out of the export before it writes anything.
        fromCatalog,
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
              reverse: undoAnswer,
              /* A group of one, to the reversal — see `Receipt.targets`. */
              targets: [
                {
                  box: row.entry.box,
                  index: row.entry.index,
                  position,
                  label: row.entry.label,
                },
              ],
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

      /* ONE POSITION AT A TIME, IN ANSWER ORDER, AND NEVER IN PARALLEL. The group write is
       * one route call because a partial WRITE must not exist; the reversal is this loop
       * over the single undo because a partial REVERSAL is real and has to be reportable
       * per position — the route's own comment argues the split. Sequential because
       * `Store.write()` takes the file lock per call, and sixteen reversals fired at once
       * stack against it and report their failures out of order — the same reason `answer`
       * serialises.
       *
       * A FINAL REFUSAL SKIPS ONE CARD AND THE LOOP GOES ON; ANYTHING ELSE STOPS IT. Final
       * (`FINAL_UNDO_CODES`) is a fact about that one answer — already reversed on the other
       * device, or held by an emitted file — and the next position knows nothing of it. A
       * dead server or a `store_busy` behind a running join will answer every remaining
       * position identically, so pressing on would collect fifteen copies of one refusal;
       * the un-walked tail stays on the receipt for another press instead. */
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

      /* `.then(ok).catch(fail)` AND NOT `.then(ok, fail)`, for the reason the other calls
       * in this file give: the two-argument form does not cover its own success handler, so a
       * throw while putting the cards back would land as an unhandled rejection with `.finally`
       * clearing `busy` — a screen that looks ready, a receipt still standing, and a card the
       * server has already reopened sitting in neither list. `walk` itself catches per
       * position, so the `.catch` below is for a failure of the bookkeeping, not of a call. */
      void walk()
        .then(({ reversed, finished, failures }) => {
          /* WHAT ACTUALLY REVERSED COMES BACK ON SCREEN, AND ONLY THAT. A position the loop
           * never reached is still answered server-side, and drawing it back would be the
           * queue disagreeing with the store about a card whose SKU is still written. */
          const done = new Set([...reversed, ...finished])
          const back = receipt.dropped.filter((row) => reversed.includes(row.entry.position))
          if (back.length > 0) putBack(back, receipt.at)

          /* The receipt SHRINKS to the tail the loop did not clear — reversed cards are back
           * on screen, finally-refused ones have no reversal left to offer — and comes down
           * whole when nothing remains. A shrunken group re-labels so the machine line keeps
           * telling receipts apart, and degrades to the last target's own label at one. */
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
                  label:
                    targets.length === 1 ? first.label : `${targets.length} still answered`,
                },
              ]
            }),
          )

          /* REPORTED PER POSITION, NEVER SILENTLY — a partly-failed group reversal names
           * every card it could not bring back. One failure keeps the server's own message
           * under the card's own label; several are joined, each prefixed with its label,
           * under a code that greps to this file the way `client_bug` does, because no one
           * server refusal produced the composite. */
          const [first] = failures
          if (first !== undefined && failures.length === 1) {
            setRefusal({ failure: first.failure, at: first.label })
          } else if (failures.length > 1) {
            setRefusal({
              failure: {
                code: 'group_undo_incomplete',
                message: failures
                  .map(({ label, failure }) => `${label}: ${failure.message}`)
                  .join(' '),
              },
              at: null,
            })
          }
        })
        .catch((err: unknown) => {
          /* The label is the receipt's and not the current card's, the same capture
           * `Refusal` argues for: the card this is about left the screen when it was
           * answered, and by now there is usually a different one on it. */
          setRefusal({ failure: describeFailure(err), at: receipt.label })
        })
        .finally(() => {
          busyRef.current = false
          setBusy(false)
        })
    },
    [putBack],
  )

  /* THE GROUP WRITE. One route call for the whole worklist, and NOTHING IS DROPPED UNTIL THE
   * SERVER ANSWERS — the opposite of `answer`, and the asymmetry is argued rather than
   * inherited. The single answer advances optimistically because docs/DESIGN.md says
   * answering advances with no acknowledgement, and the cost of being wrong is one card put
   * back; the group state is already a deliberate stop in front of a confirm, there is no
   * next card to hurry to, and optimistically clearing sixteen cards to restore them on a
   * refusal is churn with no keystroke saved. The route is all-or-nothing — a resolved
   * promise means every position landed, a rejection means none did — so this callback never
   * has a partial state to reconcile.
   *
   * THE PAIRS ARE COPIED OFF EACH ROW'S OWN LONE CANDIDATE, never composed and never shared:
   * each card answers with its own row, which is the honest reading of "the same single
   * candidate" (`groupOffer` has the argument), and the server re-validates every pair
   * against its own entry so a stale screen is caught rather than obeyed. */
  const answerGroup = useCallback(() => {
    if (busyRef.current || loadingRef.current) return
    const offer = groupOffer
    if (offer === null || rows === null) return

    const positions = new Set(offer.rows.map((row) => row.entry.position))
    const labels = new Map(offer.rows.map((row) => [row.entry.position, row.entry.label]))

    busyRef.current = true
    setBusy(true)
    setRefusal(null)

    /* `.then(ok).catch(fail)` AND NOT `.then(ok, fail)`, for the file's standing reason: the
     * success handler below walks a response body and rebuilds three pieces of state, and a
     * throw inside it has to land in the panel rather than as an unhandled rejection behind
     * a screen that looks ready. */
    void answerReviewGroup(
      offer.rows.map((row) => ({
        box: row.entry.box,
        index: row.entry.index,
        sku: row.entry.candidates[0]?.sku ?? '',
        condition: row.entry.candidates[0]?.condition ?? '',
      })),
    )
      .then((result) => {
        /* WHAT CAME BACK, RATHER THAN WHAT THIS SCREEN ASSUMED — `answer`'s rule at group
         * scale. A row is dropped only when the server names its queue cleared; today the
         * route clears every open entry it validated or refuses whole, so the predicate
         * keeps everything the group touched, and the day that stops being true the screen
         * follows the write instead of disagreeing with it silently. */
        const byPosition = new Map(result.results.map((member) => [member.position, member]))
        const clearedRow = (row: Row): boolean => {
          const member = byPosition.get(row.entry.position)
          if (member === undefined) return false
          return row.queue === 'review' ? member.review_cleared : member.parked_cleared
        }
        const dropped = rows.filter(clearedRow)
        const at = rows.findIndex(clearedRow)
        setRows((prev) => (prev === null ? prev : prev.filter((row) => !clearedRow(row))))

        /* ONE RECEIPT FOR THE GROUP (the ruling's undo is D28's shape, whole), AND ONLY WHEN
         * EVERY MEMBER CAN COME BACK. `restores_to` is the single answer's contract per
         * member, and a group undo that reverses eleven of sixteen on its best day is the
         * defect `SaleResult` records, at scale — so one held member suppresses the whole
         * control rather than arming a press that half-works. */
        const reversible = result.results.every((member) => member.restores_to !== null)
        if (reversible && dropped.length > 0) {
          remember({
            key: result.answered.join('+'),
            reverse: undoAnswer,
            targets: result.results.map((member) => ({
              box: member.box,
              index: member.index,
              position: member.position,
              label: labels.get(member.position) ?? member.position,
            })),
            /* The count and the machine string, because with several receipts standing this
             * line is the identifier — and a group's identity is its size and its reason,
             * not any one card's label. */
            label: `${result.count} cards · ${result.reason}`,
            dropped,
            at,
            said: `Answered all ${result.count} as ${result.condition}.`,
          })
        }

        /* Skips die with the cards they deferred, exactly as a single answer clears its own. */
        const answered = new Set(dropped.map((row) => row.key))
        setDeferred((prev) =>
          prev.some((key) => answered.has(key)) ? prev.filter((key) => !answered.has(key)) : prev,
        )

        /* The group is spent, so the state and the lens close together: the filter's whole
         * content was just answered, and a filter left standing over nothing would draw the
         * empty-for-this-reason note about work that is already done. */
        setGrouping(false)
        setReasonFilter(null)
      })
      .catch((err: unknown) => {
        /* NOTHING TO RESTORE — nothing was dropped. Both group refusals are in STALE_CODES,
         * so the panel below the grid draws Reload, which is the remedy their messages name;
         * the state stays open, because the grid re-derives from whatever the reload brings
         * back and closes itself if the group no longer qualifies. */
        setRefusal({ failure: describeFailure(err), at: `${positions.size} cards` })
      })
      .finally(() => {
        busyRef.current = false
        setBusy(false)
      })
  }, [groupOffer, rows, remember])

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
  /* D46 — LOOK THE CARD UP THE MOMENT IT IS DRAWN, for an entry with nothing to choose.
   *
   * The owner's ask was that the screen SUGGEST rather than wait to be asked: *"it should've
   * brought up what cards it could have matched too"*. So this runs on arrival with an empty
   * query and the server suggests from the card's own read; typing replaces it.
   *
   * UNASKED, ONLY FOR A ZERO-CANDIDATE ENTRY. A card the pipeline found rows for has an
   * answer on screen already, and fetching a catalog beside it would offer a second, looser
   * list beside a good one — which is how a screen teaches you to stop reading the first.
   *
   * D75 ADDED THE ASKED-FOR CASE, AND `looking` IS THE WHOLE OF THE DIFFERENCE. The paragraph
   * above is an argument about what appears without being sent for, and it is kept: nothing
   * changes on arrival at a card with rows. What it was ALSO doing, until 2026-08-31, was
   * deciding whether the export could be reached at all — and the entry it stranded is box 3
   * card 66, whose two candidate rows were `Get Excited!` for a photograph of Nasus, because
   * the number read as `8/298` and that is a real key in that export. The right row was in
   * the same file the whole time, and the lookup returns it FIRST.
   *
   * ONE LIST AT A TIME, WHICH IS WHY THIS IS AN OR AND THE PANEL REPLACES THE ROWS. Both
   * lists are answered on digits, so drawing them together would make `3` mean two rows.
   *
   * `cancelled` rather than an AbortController: the fetch is cheap and idempotent, and what
   * matters is only that a late answer for the previous card cannot land on this one. */
  const looking = current !== null && lookingAt === current.key
  const showCatalog = current !== null && (current.entry.candidates.length === 0 || looking)
  const lookupFor = showCatalog ? current : null
  const lookupKey = lookupFor === null ? '' : lookupFor.key
  useEffect(() => {
    setLookup(null)
    setLookupFailed(null)
    setTyped('')
    if (lookupFor === null) return
    let cancelled = false
    void reviewCatalog(lookupFor.entry.box, lookupFor.entry.index, '')
      .then((answer) => {
        if (!cancelled) setLookup(answer)
      })
      .catch((err: unknown) => {
        if (!cancelled) setLookupFailed(describeFailure(err).message)
      })
    return () => {
      cancelled = true
    }
    // `lookupKey` rather than `lookupFor`: the row object is rebuilt on every queue read, so
    // depending on it would re-fetch on a poll that changed nothing about this card. The two
    // fields this effect reads are taken out of `lookupFor` above, which is derived from the
    // same key, so the narrower dependency is the CORRECT one rather than a shortcut past the
    // rule — widening it to `lookupFor` would fetch a catalog per poll for a card nobody
    // touched.
    //
    // `looking` IS THE SECOND DEPENDENCY AND IT IS NOT REDUNDANT (D75). Pressing `L` fetches
    // for a card that has been on screen since before the press, so `lookupKey` does not
    // change and this effect would never run. It also carries the way back: Escape flips it
    // false, the effect re-runs, and the three `set` calls at the top clear the rows and the
    // typed query before the early return — so coming back to the pipeline's rows and then
    // opening the export again starts from the card's own read rather than from a stale
    // search. Both transitions are one card's, so neither can fetch for a card nobody asked
    // about.
    //
    // THE DISABLE IS NEW; THE ARGUMENT ABOVE IT IS NOT. This comment used to end "this project
    // has no exhaustive-deps rule installed, so the omission is argued here rather than silenced
    // with a disable comment for a rule that does not exist." That premise expired the day
    // `react-hooks/exhaustive-deps` was switched on in `app/eslint.config.js`, and the line
    // below is the sentence the paragraph was waiting for. A narrow disable naming its rule and
    // carrying its reason is what this repo does with an argued exception — see the two scoped
    // blocks at the foot of the eslint config.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lookupKey, looking])

  /* The typed search. Deliberately NOT debounced-on-keystroke: it is submitted, because a
   * lookup per character would fire a CSV read per keypress and because a half-typed name is
   * a different query rather than a worse one. */
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

      /* THE GROUP STATE OWNS THE KEYBOARD WHILE IT IS UP — Enter confirms, Escape leaves,
       * and every one-card branch below is dead, because the state has exactly one thing to
       * do and a digit landing on a candidate nobody can see would be a write from a screen
       * that is not showing it. R and U stay live above this line on purpose: a reload
       * re-derives the grid, and the undo acts on receipts, which are about cards already
       * gone either way. See GROUP_KEY for why these two keys and not a digit. */
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

      /* Bound only while the offer stands, like C while the skip note is up — a key that
       * does nothing most of the time is the opposite of what showing it is for. */
      if (key === GROUP_KEY && groupOffer !== null) {
        event.preventDefault()
        setGrouping(true)
        return
      }

      if (current === null) return

      /* THE CLOSE PANEL OWNS THE KEYBOARD WHILE IT IS UP, exactly as the group state does and
       * for the identical reason: its choices are keyed on digits, and a digit landing on a
       * candidate nobody can see would be a write from a screen that is not showing it. R and
       * U stay live above this line — a reload re-derives everything, and the undo acts on
       * receipts for cards already gone. */
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

      /* D75. BELOW THE CLOSE PANEL AND ABOVE THE DIGITS, which is the whole of its placement
       * argument: the panel owns the keyboard while it is up, and the digits below read
       * whichever list this key decides. */
      if (key === LOOKUP_KEY && current.entry.candidates.length > 0) {
        event.preventDefault()
        setLookingAt(looking ? null : current.key)
        return
      }

      /* The way back, and ONLY from a list the operator opened. A zero-candidate card's
       * export rows are not a state to leave — they are the only rows it has — so Escape
       * there must fall through and do nothing rather than blank the card. */
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
      /* D46 — the digits mean the SUGGESTED rows when the entry offers none of its own.
       * One vocabulary rather than two: the operator presses a number beside a row, and
       * whether the pipeline or the catalog found that row is not something the finger needs
       * to know.
       *
       * D75 — AND THE TEST IS WHAT IS DRAWN, NEVER WHAT THE ENTRY HOLDS. It was
       * `offered.length > 0` while the panel appeared only in the zero-candidate arm, so the
       * two questions had one answer and this read as the simpler of two equivalent forms.
       * They come apart the moment an entry with rows can show the export, and the wrong one
       * of the pair is a silent mis-write: the operator sees the export's third row, presses
       * `3`, and the pipeline's third row — a different card, which is why they went looking
       * — is what gets answered onto the card. `showCatalog` is the same flag the renderer
       * branches on, read here rather than re-derived, so the two cannot drift apart.
       *
       * `fromCatalog` RIDES THE SAME FLAG for the same reason: it is true exactly when the
       * row came off the export, which is exactly when this list did. */
      const candidate = showCatalog
        ? (lookup?.rows ?? [])[digit - 1]
        : current.entry.candidates[digit - 1]
      if (candidate === undefined) return
      event.preventDefault()
      answer(current, candidate, showCatalog)
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [
    current,
    answer,
    closing,
    closeCard,
    skip,
    clearSkips,
    allSkipped,
    reload,
    receipts,
    undo,
    grouping,
    groupOffer,
    answerGroup,
    // D46 — the digits read these rows when the entry offers none of its own.
    lookup,
    // D75 — and these two decide WHICH list the digits read. A handler closed over a stale
    // `showCatalog` is the mis-write the digit branch describes, arriving by a dependency
    // array instead of by a wrong comparison.
    showCatalog,
    looking,
  ])

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
        {/* THE TITLE AND THE CONTROLS SHARE A LINE. Four stacked blocks spent 169px of a 900px
            viewport before the photograph, on the screen whose whole vertical budget is the
            argument at the top of ReviewQueue.css; the measurements and the trade are in that
            file's `head` section, because this is a layout fact and not a wiring one. The DOM
            order is unchanged — heading, then its controls, then the lede — so a screen reader
            and the tab ring read exactly what they read before. */}
        <div className="review-head-top">
          <h1 className="review-title">Review queue</h1>
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
            {/* THE LENS, NAMED WHERE THE COUNTS ARE, because the two are read together: a
                16-card queue showing 3 cards is a puzzle until this span says why. The chips
                that set the filter live on the Waiting heading beside the shape they filter;
                this is only the reminder that one is on. */}
            {reasonFilter === null ? null : (
              <span className="review-count">showing only {reasonFilter}</span>
            )}
            {/* THE GROUP OFFER — drawn only while the (filtered) worklist qualifies, in the
                controls row because it costs no height there and a control this consequential
                must not be discoverable only below the photograph. Outlined, not filled: the
                fill belongs to the confirm inside the state, where it is genuinely the only
                thing to do. Pressing this writes nothing — it opens the photo-confirm state,
                which is the confirmation, and the only one (docs/DESIGN.md bans a second). */}
            {groupOffer === null || grouping ? null : (
              <button
                className="review-action"
                type="button"
                onClick={() => setGrouping(true)}
                disabled={busy || loading}
              >
                <span>Answer all {groupOffer.rows.length} as a group</span>
                <kbd className="review-key">{GROUP_KEY_LABEL}</kbd>
              </button>
            )}
          </div>
        </div>
        {/* One line, and it is one line for a reason the copy does not carry: every pixel
            of chrome on this screen pushes the candidate rows further below the fold. See
            the vertical-budget note at the top of ReviewQueue.css. Drawn at the metadata
            size beneath the row above rather than deleted — it is the only place the screen
            says that a keystroke is the whole of an answer. */}
        <p className="review-lede">
          One card at a time, worked expensive first. Answering advances; nothing asks twice.
        </p>
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
        everyone.length === 0 ? (
          <p className="review-note-text">
            Nothing is waiting. Every queued card has been answered.
          </p>
        ) : (
          /* The filter emptied the view, not the queue — reachable only with a lens on,
             since an unfiltered worklist IS everyone. Cards are still waiting behind it,
             so this states both facts and hands back the control that hid them. */
          <div className="review-note">
            <p className="review-note-text">
              Nothing is waiting for this reason. {everyone.length} other{' '}
              {everyone.length === 1 ? 'card is' : 'cards are'} still queued behind the
              filter — nothing was written to them.
            </p>
            <button
              className="review-action"
              type="button"
              onClick={() => setReasonFilter(null)}
              disabled={busy || loading}
            >
              <span>Show every reason</span>
            </button>
          </div>
        )
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

      {/* THE ONE EXCEPTION TO ONE-CARD-AT-A-TIME, in the card's own slot: the group state
          replaces the card rather than floating over it, because it IS the screen while it
          is up — the photographs it draws are the confirmation, and a card still answerable
          underneath them would be two writes armed at once. */}
      {/* THE BODY: the card (or the group offer) and the rail beside it. One wrapper, because
          the card and the group are alternatives in a single slot and the worklist is their
          SIBLING — so the grid that puts them side by side cannot live on either of them. */}
      <div className="review-body">
      {current === null ? null : grouping && groupOffer !== null ? (
        <GroupConfirm
          offer={groupOffer}
          activity={busy ? 'writing the answers' : loading ? 'rereading the queues' : null}
          onConfirm={answerGroup}
          onLeave={() => setGrouping(false)}
          refusal={refusal}
          onReload={reload}
          receipts={receiptPanel}
        />
      ) : (
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
          lookup={lookup}
          lookupFailed={lookupFailed}
          typed={typed}
          onTyped={setTyped}
          onSearch={() => searchCatalog(typed)}
          /* `true` — this row came from the catalog, not from the entry. It is the only
             call site that passes it, which is what keeps every ordinary answer unflagged. */
          onChooseCatalog={(row) => answer(current, row, true)}
          /* D75. `showCatalog` decides which list is drawn and `looking` decides what the
             control beside it says, and they are NOT the same question: a zero-candidate
             entry shows the export without anyone having asked, so it has a list to answer
             and no state to leave. */
          showCatalog={showCatalog}
          looking={looking}
          onLookup={() => setLookingAt(looking ? null : current.key)}
          onClose={() => setClosing((up) => !up)}
          closing={closing}
          onCloseChoice={(choice) => closeCard(current, choice)}
          refusal={refusal}
          onReload={reload}
          receipts={receiptPanel}
        />
      )}

      {everyone.length === 0 ? null : (
        <Waiting
          rows={everyone}
          currentKey={current?.key ?? null}
          deferred={deferred}
          filter={reasonFilter}
          onFilter={setReasonFilter}
          disabled={busy || loading}
        />
      )}
      </div>
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

  /** D46's catalog lookup, for an entry the pipeline offered no rows for. Owned by the
   *  container for `closing`'s reason: it is per-card and must be cleared by whatever
   *  replaces the card, which the card itself cannot do. */
  lookup: CatalogLookup | null
  lookupFailed: string | null
  typed: string
  onTyped: (text: string) => void
  onSearch: () => void
  onChooseCatalog: (row: CandidateRow) => void

  /** D75. Whether the export's rows are what is drawn, and whether the operator ASKED for
   *  them — two questions, because a zero-candidate entry answers yes to the first and no to
   *  the second. `showCatalog` picks the list; `looking` decides whether there is a way back
   *  and what the control offering it says. Both are the container's for `closing`'s reason,
   *  and `showCatalog` is passed rather than re-derived here so the renderer and the digit
   *  handler cannot disagree about which rows are on screen. */
  showCatalog: boolean
  looking: boolean
  onLookup: () => void

  /** D37's close panel: raise it, whether it is up, and what a choice inside it does.
   *
   *  THE PANEL IS THIS COMPONENT'S TO DRAW AND NOT ITS TO OWN, matching `receipts` above and
   *  `grouping` above that. Whether it is open is queue-level state — it has to be cleared
   *  when the card changes, which this component cannot see — so it arrives as a boolean and
   *  a pair of callbacks rather than as a `useState` in here. */
  onClose: () => void
  closing: boolean
  onCloseChoice: (choice: CloseChoice) => void

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
 * It was rendered between the header and the card. With the photo frame stacked above the
 * rows at 60vh, that puts a
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
 * ONE PANEL PER ANSWER, newest at the top. See `Receipt` for why this is a list and
 * `UNDO_DEPTH` for why they leave by being pushed out rather than by expiring.
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

/* THE GROUP STATE — docs/DECISIONS.md's one narrow exception to one-card-at-a-time, drawn.
 *
 * "A GROUP WRITE STILL SHOWS THE PHOTOGRAPHS IT IS ABOUT TO ANSWER FOR" is the ruling's own
 * condition and this grid is its discharge: every card the confirm will write is on screen,
 * with its position label, before anything can be pressed. The photographs are smaller than
 * the one-card view's — this is not the judging screen, and it must not pretend to be. The
 * judgement a group answer rests on is the one already made about the SHARED fact (Gate B:
 * sixteen normals reading as foil is one fact about the rig, not sixteen about cards), and
 * a card that needs individual comparison fails eligibility and never reaches this screen.
 * What the grid is for is the other failure: a stranger in the group — a photograph that
 * plainly is not the same kind of thing as its neighbours — which a strip of thumbnails
 * shows better than sixteen sequential full-screen views would.
 *
 * THE CONFIRM IS FILLED, AND IT IS THE FIRST AND ONLY FILL ON THIS SCREEN — decided against
 * the stylesheet's own "nothing in this file is filled" note, which was written about the
 * one-card flow and is updated beside the rule. docs/DESIGN.md reserves the solid fill for
 * a screen with exactly one thing to do, names pull-confirm and mark-sold, and bans it from
 * any screen with two answers because every way of choosing which answer to fill is biased.
 * This state HAS exactly one thing to do, and not loosely: the eligibility conditions are
 * precisely what reduce it to one — every card offers one row, of one kind, for one shared
 * reason, so there is no second answer for a fill to be biased against. "Back" is not an
 * answer, it is leaving the screen, exactly as the pull modal's way back does not unfill
 * PullConfirm. A group state that could ever offer two answers loses the fill the same
 * moment it loses its eligibility.
 *
 * NO SECOND CONFIRMATION ANYWHERE. This state IS the photo-confirm; pressing the fill
 * writes, immediately. An "are you sure" on top of it is banned by the same docs/DESIGN.md
 * rule that has always governed this screen — the photographs are what you are sure WITH.
 */
function GroupConfirm({
  offer,
  activity,
  onConfirm,
  onLeave,
  refusal,
  onReload,
  receipts,
}: {
  offer: { rows: Row[]; reason: string; condition: string }
  activity: string | null
  onConfirm: () => void
  onLeave: () => void
  refusal: Refusal | null
  onReload: () => void
  receipts: ReactNode
}) {
  const busy = activity !== null

  /* Keys whose photograph 404'd, kept per mount: the state is short-lived and re-entered
   * from live rows, so a stale entry costs one absent tile until the next reload — the
   * same trade `photoAbsent` makes, minus the single-card ambiguity it exists to solve. */
  const [absent, setAbsent] = useState<ReadonlySet<string>>(new Set())

  return (
    <section className="review-group">
      <div className="review-reason">
        <p className="review-reason-label">{reasonLabel(offer.reason)}</p>
        {/* The machine string and the size, greppable against review.json and the run
            report exactly as the one-card view keeps it. */}
        <p className="review-machine">
          {offer.reason} · {offer.rows.length} cards
        </p>
      </div>

      {/* The sentence: what one press does, and what it does not. The values are in the
          utility face for the file's standing reason — a condition string set in prose has
          stopped being greppable. */}
      <p className="review-sentence">
        Every card below offers exactly one row —{' '}
        <span className="review-claim">{offer.condition}</span> — for the same reason. One
        press answers each card with its own row; nothing is guessed and nothing is shared
        between them.
      </p>

      <ul className="review-group-grid">
        {offer.rows.map((row) => (
          <li key={row.key} className="review-group-cell">
            {row.entry.box < 1 || row.entry.photo === null || absent.has(row.key) ? (
              /* The absent states collapse to one tile here — which of the three it is
                 matters on the judging screen and is drawn there; on a strip whose job is
                 "is anything in this group not like the others", a missing photograph is
                 one fact, and it is exactly the kind of stranger the grid exists to shows. */
              <span className="review-group-absent">no photo</span>
            ) : (
              <img
                className="review-group-photo"
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
            <span className="review-group-pos">{row.entry.label}</span>
          </li>
        ))}
      </ul>

      <div className="review-actions">
        <button
          className="review-group-confirm"
          type="button"
          onClick={onConfirm}
          disabled={busy}
        >
          <span>
            Answer all {offer.rows.length} as {offer.condition}
          </span>
          <kbd className="review-key">Enter</kbd>
        </button>
        {/* Leaving writes nothing and forgets nothing — the cards are exactly where they
            were, one at a time. Quiet by construction, like Skip: it must not look like an
            answer. */}
        <button className="review-action" type="button" onClick={onLeave} disabled={busy}>
          <span>Back to one at a time</span>
          <kbd className="review-key">Esc</kbd>
        </button>
        {activity === null ? null : <span className="review-busy">{activity}</span>}
      </div>

      {/* The same slot the one-card view gives them, for the same reasons: a refusal about
          the press just made, then the receipts about cards already gone. */}
      {refusal === null ? null : (
        <RefusalPanel refusal={refusal} onReload={onReload} disabled={busy} />
      )}
      {receipts}
    </section>
  )
}

/* Photo first, then the finding, then the rows — the photograph in its own grid track and
 * the finding, rows, panels, actions and facts in theirs, side by side above 900px and
 * stacked below it. docs/DESIGN.md rejected a left/right split by name until 2026-08-24 and
 * now carries the measurement that reversed it. */
type CatalogPanelProps = {
  lookup: CatalogLookup | null
  failed: string | null
  typed: string
  onTyped: (text: string) => void
  onSearch: () => void
  onChoose: (row: CandidateRow) => void
  /** D75 — whether these rows are STANDING IN FOR a list the operator rejected, rather than
   *  standing where the pipeline left a hole. It changes one paragraph of copy and nothing
   *  else: the rows, the digits and the search are identical in both cases. */
  overruling: boolean
  busy: boolean
}

/** D46 — what this card could be, when the pipeline offered nothing.
 *
 *  THREE STATES AND THEY SAY DIFFERENT THINGS, which is the whole reason `lookup` is null
 *  until the fetch answers rather than starting as an empty array: "still looking", "the
 *  export holds nothing like this" and "here are the rows" are three different sentences, and
 *  collapsing the first two teaches the operator that a slow fetch means a card that matches
 *  nothing.
 *
 *  THE ROWS REUSE `.review-candidate` EXACTLY. A row a person found and a row the join found
 *  look identical once they are on screen and are answered by the same digit — see the
 *  keyboard handler. Giving these their own look would be inventing a second vocabulary for
 *  the one gesture this screen is built around.
 *
 *  THE SEARCH IS A FORM, so Enter submits it and the browser says so without a key hint. The
 *  keyboard handler ignores keystrokes inside an editable target (`isEditableTarget`), which
 *  is what stops a typed `1` from answering the card. */
function CatalogPanel({
  lookup,
  failed,
  typed,
  onTyped,
  onSearch,
  onChoose,
  overruling,
  busy,
}: CatalogPanelProps): ReactNode {
  const rows = lookup?.rows ?? []
  return (
    <div className="review-catalog">
      {/* TWO SENTENCES FOR TWO SITUATIONS, AND THE DIFFERENCE IS WORTH THE BRANCH (D75). The
          rows are identical either way, so the copy is the only place the screen can say
          whether the pipeline had nothing to offer or had something wrong — and those call
          for opposite amounts of trust in the list underneath. The overruling sentence names
          the mechanism that produced the bad rows, because a number that matched the wrong
          card is the failure this arm exists for and it is invisible from the rows. */}
      {overruling ? (
        <p className="review-note-text">
          The rows the pipeline offered are still there behind this — press {LOOKUP_KEY_LABEL}{' '}
          or Escape to go back to them. These are rows from the same export, matched on the
          name the model read rather than on its number, which is what a wrong number gets
          wrong. A person has to say which, if any, is right.
        </p>
      ) : (
        <p className="review-note-text">
          The pipeline found no row for this card, so it has nothing of its own to offer.
          These are rows from the export it was joined against, matched on what the model read
          — a person has to say which, if any, is right.
        </p>
      )}

      {failed !== null ? (
        <p className="review-catalog-empty">{failed}</p>
      ) : lookup === null ? (
        <p className="review-catalog-empty">Looking in the export…</p>
      ) : rows.length === 0 ? (
        <p className="review-catalog-empty">
          Nothing in that export matches {lookup.query ? `“${lookup.query}”` : 'this card'}.
          Search for it by name, collector number or SKU, or close the card below.
        </p>
      ) : (
        <ul className="review-candidates">
          {rows.map((row, at) => (
            <li key={`${row.sku}:${at}`}>
              <button
                type="button"
                className="review-candidate"
                onClick={() => onChoose(row)}
                disabled={busy}
              >
                {at < MAX_KEYED_CANDIDATES ? (
                  <kbd className="review-key">{at + 1}</kbd>
                ) : (
                  <span className="review-key-blank">–</span>
                )}
                <span className="review-candidate-name">{row.name}</span>
                <span className="review-candidate-condition">{row.condition}</span>
                <span
                  className={
                    row.market ? 'review-candidate-price' : 'review-candidate-price is-unpriced'
                  }
                >
                  {row.market ? priceText(row.market) : 'no market price'}
                </span>
                <span className="review-candidate-meta">
                  {row.set} · {row.number}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {lookup !== null && lookup.truncated ? (
        <p className="review-catalog-more">
          {lookup.found} rows match; the first {rows.length} are shown, because the digits
          stop at {MAX_KEYED_CANDIDATES}. Narrow the search to see the rest.
        </p>
      ) : null}

      <form
        className="review-catalog-search"
        onSubmit={(event) => {
          event.preventDefault()
          onSearch()
        }}
      >
        <label className="review-catalog-label" htmlFor="review-catalog-q">
          Search this export
        </label>
        <input
          id="review-catalog-q"
          className="review-catalog-input"
          type="search"
          value={typed}
          placeholder="name, collector number, or SKU"
          onChange={(event) => onTyped(event.target.value)}
          disabled={busy}
        />
        <button type="submit" className="review-action" disabled={busy}>
          Search
        </button>
      </form>
    </div>
  )
}

function Card({
  row,
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
      {/* THE STAGE. Its own element because the photograph is now a grid TRACK rather than the
          first item of a column, and because sticky needs a box of its own to stick. */}
      <div className="review-stage">
        <Photo row={row} absent={photoAbsent} onAbsent={onPhotoAbsent} />
      </div>

      {/* THE CHOICE COLUMN, WHICH IS WHAT `.review-card` USED TO BE. Everything below is
          unmoved and un-retuned: same order, same measure, same flex column with
          `align-items: flex-start`. Only its position relative to the photograph changed. */}
      <div className="review-choice">
      {/* WHERE IT IS AND WHY IT IS HERE, ON ONE LINE. Stacked, these two cost 110px of the
          gap between the photograph and the candidate rows — on a screen that had the third
          candidate row 12px below a 900px fold. Side by side they cost 68px and the whole
          choice fits on screen with the photograph, which is the comparison this screen
          exists to make. Nothing about the pair changes: the label is still the human one
          with the machine string beneath it, at the sizes docs/DESIGN.md sets. */}
      <div className="review-card-head">
        <p className="review-position">
          <PositionLabel label={entry.label} />
        </p>

        <div className="review-reason">
          {/* Accent at outline and text weight: the system is unsure. The chip carries the
              human label; the machine string sits beneath it, lowercase and unstyled beyond
              the utility face, because it has to grep against the run report and review.json
              exactly as it reads here. */}
          <p className="review-reason-label">{reasonLabel(entry.reason)}</p>
          <p className="review-machine">{entry.reason}</p>
        </div>
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

      {showCatalog ? (
        /* D46 — THE CARD THE PIPELINE FOUND NOTHING FOR, WHICH IS NO LONGER A DEAD END.
           This arm drew one paragraph of prose until 2026-08-29: it said the only move was to
           skip, and pointed at a command in a terminal. Both halves had gone stale. D37 had
           put a stand-down on this very screen and the copy never mentioned it, and the row
           the pipeline missed was usually sitting in the export the whole time.

           THE PANEL GOES IN THE ROWS' OWN SLOT, not below them, and that is what keeps
           `ReviewQueue.css`'s rule intact: nothing may come between the sentence and the
           rows. These ARE the rows — found by a catalog lookup rather than by the join, drawn
           through the same markup, answered on the same digits. The difference that matters is
           carried by the copy above them, not by the shape of the row.

           The prose that survives says what is true and what to do, in that order. */
        <CatalogPanel
          lookup={lookup}
          failed={lookupFailed}
          typed={typed}
          onTyped={onTyped}
          onSearch={onSearch}
          onChoose={onChooseCatalog}
          overruling={looking}
          busy={activity !== null}
        />
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

      {/* D37's panel, above the actions that raise it and below the candidate rows — so the
          thing it is about (this card) is still on screen, and the rows it is an alternative
          to are still readable above it. It replaces nothing while it is up. */}
      {!closing ? null : (
        <div className="review-close" role="group" aria-label="Close this card without answering it">
          <p className="review-close-lede">
            Neither of these identifies the card. Both stop the queue asking about it, for good.
          </p>

          <p className="review-close-head">
            Stand down · <span className="review-close-note">the card stays exactly where it is</span>
          </p>
          {CLOSE_CHOICES.map((option, at) =>
            option.choice.kind !== 'stand_down' ? null : (
              <button
                key={option.machine}
                className="review-close-choice"
                type="button"
                onClick={() => onCloseChoice(option.choice)}
                disabled={busy}
              >
                <kbd className="review-key">{at + 1}</kbd>
                <span className="review-close-label">{option.label}</span>
                <span className="review-machine">{option.machine}</span>
                <span className="review-close-why">{option.note}</span>
              </button>
            ),
          )}

          <p className="review-close-head">
            Retire · <span className="review-close-note">the card leaves inventory, its slot stays empty</span>
          </p>
          {CLOSE_CHOICES.map((option, at) =>
            option.choice.kind !== 'retire' ? null : (
              <button
                key={option.machine}
                className="review-close-choice"
                type="button"
                onClick={() => onCloseChoice(option.choice)}
                disabled={busy}
              >
                <kbd className="review-key">{at + 1}</kbd>
                <span className="review-close-label">{option.label}</span>
                <span className="review-machine">{option.machine}</span>
                <span className="review-close-why">{option.note}</span>
              </button>
            ),
          )}

          {/* THE ONE THAT IS NOT HERE, SAID OUT LOUD. The owner asked for a delete on this
              screen; it lives on Inventory because it slides every card behind it down a slot,
              which would renumber the worklist this panel is drawn from, and because it is the
              one operation here with no undo at all. Saying so is cheaper than letting someone
              hunt for it and conclude it does not exist. */}
          <p className="review-close-elsewhere">
            Deleting the capture and reclaiming the slot is on the Inventory screen. It
            renumbers every card behind this one and cannot be undone, so it is not offered
            from a worklist.
          </p>
        </div>
      )}

      <div className="review-actions">
        {/* Skip is the only control on this screen that is not a candidate row, and it is the
            only way past a card that cannot be answered — see the no-candidates note above.
            Quiet by construction: it writes nothing, so it must not look like an answer. */}
        <button className="review-action" type="button" onClick={onSkip} disabled={busy}>
          <span>Skip</span>
          <kbd className="review-key">{SKIP_KEY_LABEL}</kbd>
        </button>

        {/* D75. BEFORE "Close this card", WHICH IS THE POINT OF WHERE IT SITS. The two
            controls beside it are both ways PAST a card; this is a second way to ANSWER one,
            and offering it after the two exits reads as a last resort when it is the first
            thing to reach for once the rows on screen are visibly the wrong card.

            ONLY WHERE THERE IS SOMETHING TO OVERRULE. A zero-candidate entry is already
            showing the export, so the control would toggle between one list and the same
            list — and `onLookup` is bound to a key that does nothing there for the same
            reason. Outline, never a fill: this screen still has more than one thing to do,
            which is docs/DESIGN.md's test and not this control's. */}
        {entry.candidates.length === 0 ? null : (
          <button
            className="review-action"
            type="button"
            onClick={onLookup}
            disabled={busy}
            aria-expanded={looking}
          >
            <span>{looking ? "Back to the pipeline's rows" : 'None of these — search the export'}</span>
            <kbd className="review-key">{LOOKUP_KEY_LABEL}</kbd>
          </button>
        )}

        {/* D37. Beside Skip because they are the two ways past a card that is not being
            answered, and the difference between them is exactly what the panel exists to
            say: Skip forgets on reload, this one is permanent. Also an outline and never a
            fill — docs/DESIGN.md reserves the solid fill for a screen with exactly one thing
            to do, and this screen always has the candidates too. */}
        <button
          className="review-action"
          type="button"
          onClick={onClose}
          disabled={busy}
          aria-expanded={closing}
        >
          <span>Close this card</span>
          <kbd className="review-key">{CLOSE_KEY_LABEL}</kbd>
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
      </div>
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
    { label: 'Toggle', value: claimMembers(entry.read.metadata_finish)?.join(' · ') ?? 'no claim' },
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
  /* Declared before every early return below, because hooks are. The aim is in NATURAL pixel
     coordinates, which every stored frame shares (2160x3840), so it stays meaningful across an
     advance: answer a card with the keyboard while hovering and the glass shows the next
     card's same region rather than blinking out. `onPointerLeave` is what clears it. */
  const [aim, setAim] = useState<LoupeAim | null>(null)

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
    <>
      <img
        // Remounted per card, so a failed load cannot leave the previous card's broken state
        // attached to the next one's element.
        key={row.key}
        className="review-photo"
        src={src}
        alt={`The card photographed at ${entry.label}`}
        onError={onAbsent}
        // The loupe aims off THIS element rather than off a copy of it: one <img>, one box,
        // one set of natural dimensions, so the glass cannot drift from the photograph it is
        // magnifying. `draggable` off because a drag inside the frame is a pointer gesture
        // the browser would otherwise turn into a ghost image of the card.
        draggable={false}
        onPointerMove={(event) => setAim(loupeAim(event.currentTarget, event.clientX, event.clientY))}
        onPointerLeave={() => setAim(null)}
      />
      {/* THE 1:1 INSET, AND IT IS THE ONE THING ON THIS SCREEN THAT CHANGES WHAT A HUMAN CAN
          ACTUALLY SEE RATHER THAN HOW FAR THEY REACH.

          The stored frame is 2160x3840 and draws 415px wide — a 5.2:1 downscale. Both
          digitization standards this project's capture side already follows require this
          class of judgement at native resolution: FADGI, that evaluation "shall be conducted
          while viewing the images at a 1 to 1 pixel ratio or 100% magnification"; Metamorfoze
          the same, at 100% on a calibrated monitor.

          It is not academic here. The human on this screen is the appeal court for a detector
          that was wrong on 230 of 544 box-2 cards with the owner supplying ground truth, and
          19 of 40 frames DISAGREED WITH THEMSELVES between max-edge 900 and 1200 — direct
          evidence that sheen does not survive a downscale. Asking someone to rule on foil from
          a 5.2:1 render is asking them to judge on evidence the standards say is gone.

          A background-image rather than a canvas or a second <img>: `background-size: auto`
          paints the file at its natural size and `background-position: center` picks the
          middle of it, which IS 1:1 with no arithmetic, no second request — the browser has
          the bytes already — and nothing to keep in step with the photograph beside it.

          aria-hidden because it is the same photograph at a different magnification; the <img>
          above carries the alt text, and a screen reader announcing the card twice is noise. */}
      {aim === null ? null : (
        <span
          className="review-inset"
          style={{
            backgroundImage: `url(${src})`,
            backgroundPosition: `${-aim.bx}px ${-aim.by}px`,
            left: `${aim.x - LOUPE / 2}px`,
            top: `${aim.y - LOUPE / 2}px`,
          }}
          aria-hidden="true"
        />
      )}
    </>
  )
}

/* THE LOUPE, AND IT MOVES (owner, 2026-08-24).
 *
 * It used to be a fixed 240x180 inset pinned bottom-right, showing the centre of the stored
 * frame at 1:1 with `background-position: center`, and `pointer-events: none` on the grounds
 * that "it is evidence, not a control". The owner, looking at it over a Crawdaunt:
 *
 *     "resolve this zoom thing we have going on here, i'm kinda confused as to what i'm
 *      supposed to be looking at"
 *
 * They were right, and the fixed aim is the whole defect. The centre of a 2160x3840 frame is
 * the middle of the card's artwork — on that Crawdaunt, the Pokedex data strip reading
 * `NO. 0342 Rogue Pokemon HT: 3'7"`. That region decides NOTHING. Worse, `0342` is exactly the
 * National Pokedex number D35 records the model misreading as a collector number, so the one
 * thing the inset magnified was the string that caused the error it was sitting beside.
 *
 * A FIXED AIM CANNOT BE RIGHT, and D32 already argued why in a different context: the card
 * occupies 39% to 81% of the frame across one box, because cards move on the tray. Any
 * constant offset is a guess that is wrong per frame. The detector knows where the card is;
 * a CSS percentage never can.
 *
 * So the aim becomes the operator's. Pointer inside the photograph moves the loupe to what is
 * under it, at 1:1 — which reaches the collector number, the set code, the rarity symbol and
 * the sheen, rather than committing to one of them forever.
 *
 * WHAT THIS DOES NOT REOPEN. `docs/DESIGN.md` bans a list -> detail -> back loop on this
 * screen, and the old comment leaned on that ban to keep the inset inert. A hover loupe is
 * not that loop: nothing is navigated, nothing is clicked, no state survives the pointer
 * leaving, and every key on this screen does exactly what it did before. The keyboard flow —
 * digits, `G`, `S`, `U` — is untouched, so the mouse is an addition and never a requirement.
 *
 * 1:1 IS PRESERVED, and it is the reason this element exists at all. `background-size: auto`
 * paints the file at natural size; the offset below picks which natural pixel sits under the
 * pointer. FADGI and Metamorfoze both require this class of judgement at 100% magnification,
 * and the detector was wrong on 230 of 544 box-2 cards while 19 of 40 frames disagreed with
 * themselves between two downscales — so a human ruling from a 5.2:1 render is ruling on
 * evidence the standards say is already gone.
 *
 * HIDDEN AT REST. The confusion the owner reported was an unexplained crop sitting on the
 * photograph at all times; a loupe that appears under the pointer explains itself by moving.
 * `.review-photo` has no `object-fit`, so the <img> box IS the drawn image and the pointer
 * maps to it with no letterbox arithmetic. */
/* The loupe's diameter, in CSS px, and the one number both sides of the aim must agree on:
   the element is drawn this wide and the background is offset by half of it, so a change here
   moves the glass and its contents together. Kept in TS rather than read back out of the
   stylesheet because the offset arithmetic below needs it as a number. */
const LOUPE = 220

type LoupeAim = { x: number; y: number; bx: number; by: number }

function loupeAim(img: HTMLImageElement, clientX: number, clientY: number): LoupeAim | null {
  const box = img.getBoundingClientRect()
  const x = clientX - box.left
  const y = clientY - box.top
  if (x < 0 || y < 0 || x > box.width || y > box.height) return null
  /* `naturalWidth` is 0 until the image decodes, so a pointer that arrives first gets no
     loupe rather than a divide-by-zero aim. */
  if (img.naturalWidth === 0 || img.naturalHeight === 0 || box.width === 0) return null
  const nx = (x / box.width) * img.naturalWidth
  const ny = (y / box.height) * img.naturalHeight
  return { x, y, bx: nx - LOUPE / 2, by: ny - LOUPE / 2 }
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
  filter,
  onFilter,
  disabled,
}: {
  rows: Row[]
  currentKey: string | null
  /** In skip order, which is the order the tail of this list is in. */
  deferred: readonly string[]
  /** The active reason lens, or null for every reason. The chips below set it, because the
   *  shape line is where a queue's composition is read and "work one reason at a time" is a
   *  decision made while reading it. */
  filter: string | null
  onFilter: (reason: string | null) => void
  disabled: boolean
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
   * asked for. Every pixel above the card pushed the candidate rows further below the fold —
   * they started at y=911 of 900 at 1440x900 before the split of 2026-08-24 put them beside
   * the photograph, and the reason survives the fix: this heading is beside the card rather
   * than above it, so it still costs the rows nothing — and this list is where a shape is read
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
            same string, and against the run report, which carries it again.

            A BUTTON SINCE THE GROUP DECISION, because the shape line is where "work one
            reason at a time" gets decided and the control belongs where the decision is
            made. Pressing a chip narrows the screen to that reason; pressing it again — or
            the every-reason chip that appears beside it — widens it back. The chip writes
            nothing: the lens is this screen's, the files never hear about it. The ROWS
            below stay unpressable — the no-navigation rule is about them, and a filtered
            list is still an order, not a menu. */}
        {shape.map(([reason, n]) => (
          <button
            className="review-waiting-shape"
            type="button"
            key={reason}
            aria-pressed={filter === reason}
            onClick={() => onFilter(filter === reason ? null : reason)}
            disabled={disabled}
          >
            {n} {reason}
          </button>
        ))}
        {filter === null ? null : (
          <button
            className="review-waiting-shape"
            type="button"
            aria-pressed={false}
            onClick={() => onFilter(null)}
            disabled={disabled}
          >
            every reason
          </button>
        )}
      </h2>
      <ul className="review-waiting-list">
        {rows.map((row) => (
          <li
            key={row.key}
            className="review-row"
            data-band={bandOf(row.entry.market)}
            data-parked={row.queue === 'parked' ? 'true' : undefined}
            /* Behind the lens, not gone: hiding a waiting card would make the shape chips
               lie about a queue the count line still sums, so it dims instead — the parked
               treatment, for the same reason it works there: "not what you are working on"
               is a fact about emphasis, never about existence. */
            data-filtered-out={filter !== null && row.entry.reason !== filter ? 'true' : undefined}
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
