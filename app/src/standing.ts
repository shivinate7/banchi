import type { IconName } from './kit'
import type {
  OrdersPayload,
  PricingCorpus,
  PricingSku,
  PricingWorklist,
  RunSummary,
  ServerStatus,
  WithheldRecord,
} from './types'

/* THE STANDING LINE — what the store is waiting on, ranked, as one sentence.
 *
 * This is a POLICY and it lives in its own module for that reason. The order below decides
 * what the front page of this product says every time it is opened, and a ranking buried in a
 * component is one nobody can find, argue with, or test. `Home.tsx` renders what this returns
 * and makes no judgement of its own.
 *
 * WHY IT REPLACED A COUNT. The lede used to say how many cards were on hand in how many boxes.
 * Every figure in it was drawn again by the six-stage spine 24px below, was already known to
 * the only person who writes to this store, and was unchanged between most two consecutive
 * openings. This line answers a different question — what will not fix itself — and the test
 * it has to pass is whether reading it changes what the operator does in the next ten minutes.
 *
 * ─── THE NULL INVARIANT, which is the part that is easy to get wrong ────────────────────────
 *
 * There are THREE distinct non-values here and they are not the same fact:
 *
 *   loading   — the request has not landed
 *   failed    — the request did not answer
 *   refused   — the server answered and declined to count (`queues.review` is `number | null`
 *               on purpose; `types.ts` is explicit that a reader must render the gap and never
 *               coerce the null to zero, because a count that is wrong in the direction of
 *               "there is nothing to do" is worse than no count at all)
 *
 * Each is ranked AT THE ROW IT WOULD HAVE ANSWERED, so an unknown never sorts below a known
 * zero. And `ok` — "Clear, nothing is owed anywhere" — is reachable ONLY from a complete
 * reading. Green can never be painted over a gap. That is the whole invariant and every branch
 * below is written to keep it.
 */

export type StandingTone = 'danger' | 'warn' | 'live' | 'ok' | 'none'

/** A run of the sentence. `em` is a figure, and draws in ink with tabular numerals. */
export type Say = { readonly text: string; readonly em?: boolean }

/** One item of the quieter line under the sentence: what is queued behind the head. */
export type Behind = { readonly figure: string | null; readonly label: string }

export type Standing = {
  /** Stable across renders for the same condition, so React does not re-mount on a re-poll. */
  readonly key: string
  readonly tone: StandingTone
  /** Absent where the row is prose rather than a control — see `href`. */
  readonly icon: IconName | null
  /** The coloured opening words: "Waiting on you", "Working", "Clear". */
  readonly lead: string
  readonly say: readonly Say[]
  /** Null when this row cannot be pressed, which is what makes it prose and not a control. */
  readonly href: string | null
  readonly kbd: string | null
  readonly behind: readonly Behind[]
  /** The server's own `problem` string, shown verbatim and never paraphrased. */
  readonly problem: string | null
  /** True while a run is running, which is the only thing that may paint the ribbon live. */
  readonly running: boolean
}

/** What every reader hands in. `null` means loading; a failed read is its own flag. */
export type StandingInput = {
  readonly status: ServerStatus | null
  readonly statusFailed: boolean
  readonly orders: OrdersPayload | null
  readonly ordersFailed: boolean
  readonly pricing: PricingWorklist | null
  readonly pricingFailed: boolean
  readonly runs: readonly RunSummary[] | null
  readonly runsFailed: boolean
  /** Copies written to a file and not yet found at TCGplayer (`GET /pipeline/sends`), or null
   *  where that was not read — the demo, an older server. Null never reads as zero. */
  readonly unconfirmed?: number | null
  /** The store's pricing answers (`GET /pricing`), which the ready count reads per SKU. Null
   *  while loading, like every reading above. */
  readonly book?: PricingCorpus | null
  readonly bookFailed?: boolean
}

/** A held or unlisted answer: the row stays back on purpose. */
export function isWithheld(value: unknown): value is WithheldRecord | 'unlisted' {
  return value === 'unlisted' || (typeof value === 'object' && value !== null && 'withheld' in value)
}

/** The answer the corpus holds for a row, read the way `#/pricing` reads it: a row with no
 *  market price reads the `unknown` channel, every other row reads the rest. */
export function corpusAnswer(book: PricingCorpus, row: Pick<PricingSku, 'sku' | 'bucket'>): unknown {
  const answer = (book.skus ?? {})[row.sku]
  if (answer === null || answer === undefined) return undefined
  return (answer.channel === 'unknown') === (row.bucket === 'no_market_data') ? answer.value : undefined
}

/** THE BAR'S RULE FOR ONE ROW, AND HOME READS THE SAME ONE (the delta review, R4 F1). The
 *  copies a send carries for this row, and whether the row owes a price. A row with no market
 *  price and no answer is left out of the send and stays on the list (the owner's Q3 ruling),
 *  so it owes a price and sends nothing. */
export function rowShare(
  row: Pick<PricingSku, 'bucket' | 'at_cap' | 'add_to_quantity'>,
  answer: unknown,
): { ready: number; needsPrice: boolean } {
  if (row.at_cap || isWithheld(answer)) return { ready: 0, needsPrice: false }
  if (row.bucket === 'no_market_data' && typeof answer !== 'string') return { ready: 0, needsPrice: true }
  return { ready: row.add_to_quantity, needsPrice: false }
}

/** The `owes` reason `_run_owes` adds for a card left out of the send for want of a price. It
 *  owes a price and does not block the run, so it never counts as a run that cannot be sent. */
const LEFT_OUT_FOR_PRICE = / with no market price needs? a price$/

/** THE ONE `owes` REASON THAT IS NOT A PRICE. `server/pipeline_routes.py:_run_owes` appends it
 *  to a joined run that has never written a file: the run waits on the SEND, and counting it
 *  as "to price" is what had Home say "2 runs to price" while Pricing said "Ready" (UX-006). */
const NOT_YET_WRITTEN = 'never emitted'

/** Runs that owe a PRICE, not only the send. ONE COUNT FOR HOME'S LINE AND HOME'S TILE, so the
 *  two cannot say different things about the same runs (UX-006; D198's one-figure rule). */
export function runsOwingPrice(roster: PricingWorklist['roster']): number {
  return roster.filter((r) => r.open && r.owes.some((reason) => reason !== NOT_YET_WRITTEN)).length
}

const n = (v: number): Say => ({ text: v.toLocaleString(), em: true })
const t = (text: string): Say => ({ text })

/** A reading that could not be taken, ranked where the answer would have been. */
function unknown(key: string, message: string, problem: string | null): Standing {
  return {
    key,
    tone: 'warn',
    icon: 'alert',
    lead: 'Cannot tell',
    say: [t(` — ${message}`)],
    href: null,
    kbd: null,
    behind: [],
    problem,
    running: false,
  }
}

export function standing(input: StandingInput): Standing | null {
  const { status, orders, pricing, runs } = input

  /* Nothing is decided until the status has landed: it carries the card count that separates
     a fresh store from a store whose readers are merely slow, and every branch below reads
     one of the two. */
  if (status === null) return input.statusFailed
    ? unknown('status-failed', 'the server did not answer.', null)
    : null

  const problem = status.problem ?? null

  /* 0 — a store with no cards in it has no queue to rank, and says so rather than reporting
         that nothing is owed. Those are different sentences and only one of them is true. */
  if (status.cards === 0) {
    return {
      key: 'fresh',
      tone: 'none',
      icon: 'camera',
      lead: 'Nothing yet',
      say: [t(' — the queue starts at the camera.')],
      href: null,
      kbd: null,
      behind: [{ figure: null, label: 'Boxes are made as you fill them.' }],
      problem,
      running: false,
    }
  }

  /* Everything below needs the queue depths and the ledger. Read them once, and keep the
     three non-values apart. */
  const review = status.queues.review
  const parked = status.queues.parked
  const open = orders === null ? null : orders.orders.filter((o) => o.open)
  const toPull = open === null ? null : open.reduce((sum, o) => sum + Math.max(0, o.wanted - o.recorded), 0)
  /* `resolution.orders` is a SUBSET of `orders` keyed on the ledger's own `open_keys`
     (`server/capture_server.py:do_orders`, D63 amended) — a Canceled or already-shipped
     order is excluded from it before this ever runs. This still joins by KEY against `open`
     rather than trusting that shape blind: `open` is the one field this module is allowed to
     read (D114 — no status vocabulary in `app/`), so a resolution row is counted only where
     its own order reads `open: true` on the wire, never derived from `status` text and never
     assumed pre-filtered. See `## D202`. */
  const openKeys = open === null ? null : new Set(open.map((o) => o.key))
  const unfindable =
    orders === null || openKeys === null
      ? null
      : orders.resolution.orders.reduce((sum, o) => sum + (openKeys.has(o.key) ? (o.outstanding ?? 0) : 0), 0)
  const owed = pricing === null ? null : runsOwingPrice(pricing.roster)
  /* WHAT IS READY, AND WHAT OWES A PRICE: `#/pricing`'s bar rule, per SKU (R4 F1). A run with
     one unpriced card still sends its priced ones, so the count is never per run. */
  const book = input.book ?? null
  let readyCopies: number | null = null
  let needsPrice: number | null = null
  if (pricing !== null && book !== null) {
    readyCopies = 0
    needsPrice = 0
    for (const row of pricing.skus ?? []) {
      const share = rowShare(row, corpusAnswer(book, row))
      readyCopies += share.ready
      if (share.needsPrice) needsPrice += 1
    }
  }
  /* A run whose own reason stops the whole send (the cut-off price unset), apart from a card
     left out for want of a price and from a run that only waits on the send. */
  const blocked =
    pricing === null
      ? null
      : pricing.roster.filter(
          (r) => r.open && r.owes.some((reason) => reason !== NOT_YET_WRITTEN && !LEFT_OUT_FOR_PRICE.test(reason)),
        ).length
  const unconfirmed = input.unconfirmed ?? null
  const live = runs === null ? null : runs.filter((r) => r.live)

  const behind: Behind[] = []
  const add = (figure: number | null, label: string, when: boolean) => {
    if (when) behind.push({ figure: figure === null ? null : figure.toLocaleString(), label })
  }

  /* 1 — copies a buyer has already paid for that this store cannot find anywhere. The only
         condition on this screen that is genuinely bad news, and until now it was tail text
         inside a stage note. */
  if (unfindable !== null && unfindable > 0) {
    add(toPull, 'copies to pull', toPull !== null && toPull > 0)
    add(review, 'to review', review !== null && review > 0)
    add(owed, 'runs to price', owed !== null && owed > 0)
    return {
      key: 'unfindable',
      tone: 'danger',
      icon: 'alert',
      lead: 'Cannot be filled',
      say: [
        t(' — '),
        n(unfindable),
        t(unfindable === 1 ? ' copy for ' : ' copies for '),
        n(open === null ? 0 : open.length),
        t(open !== null && open.length === 1 ? ' open order cannot be found.' : ' open orders cannot be found.'),
      ],
      href: '#/orders',
      kbd: ',O',
      behind,
      problem,
      running: live !== null && live.length > 0,
    }
  }
  if (orders === null) {
    return unknown(
      'orders-unknown',
      input.ordersFailed ? 'the order ledger did not answer.' : 'the order ledger is still loading.',
      problem,
    )
  }

  /* 2 — copies an open order wants that are still in a box. */
  if (toPull !== null && toPull > 0) {
    add(review, 'to review', review !== null && review > 0)
    add(owed, 'runs to price', owed !== null && owed > 0)
    return {
      key: 'pull',
      tone: 'warn',
      icon: 'cart',
      lead: 'Waiting on you',
      say: [
        t(' — pull '),
        n(toPull),
        t(toPull === 1 ? ' copy for ' : ' copies for '),
        n(open!.length),
        t(open!.length === 1 ? ' open order.' : ' open orders.'),
      ],
      href: '#/orders',
      kbd: ',O',
      behind,
      problem,
      running: live !== null && live.length > 0,
    }
  }

  /* 3 — the review queue. A refusal to count ranks HERE rather than falling through to a
         cheerful "nothing is owed", which is the whole reason the wire types it nullable. */
  if (review === null) {
    return unknown('review-unknown', 'the review queue could not be counted.', problem)
  }
  if (review > 0) {
    add(owed, 'runs to price', owed !== null && owed > 0)
    add(parked, 'parked', parked !== null && parked > 0)
    return {
      key: 'review',
      tone: 'warn',
      icon: 'inbox',
      lead: 'Waiting on you',
      say: [t(' — answer the '), n(review), t(review === 1 ? ' card waiting in Review.' : ' cards waiting in Review.')],
      href: '#/review',
      kbd: ',Q',
      behind,
      problem,
      running: live !== null && live.length > 0,
    }
  }

  /* 4 — the pricing worklist: what is ready to send, and what owes a price. */
  if (pricing === null || readyCopies === null || needsPrice === null || blocked === null) {
    return unknown(
      'pricing-unknown',
      input.pricingFailed || input.bookFailed
        ? 'the pricing worklist did not answer.'
        : 'the pricing worklist is still loading.',
      problem,
    )
  }

  /* 4a — ready copies wait on the send, which is one press on Pricing (`D273`). A card that
         owes a price does not stop it (Q3), so it is named behind the line, never in front. */
  if (readyCopies > 0) {
    add(needsPrice, needsPrice === 1 ? 'card needs a price' : 'cards need a price', needsPrice > 0)
    add(blocked, blocked === 1 ? 'run needs its cut-off price' : 'runs need their cut-off price', blocked > 0)
    return {
      key: 'send',
      tone: 'warn',
      icon: 'send',
      lead: 'Waiting on you',
      say: [t(' — send '), n(readyCopies), t(readyCopies === 1 ? ' copy to TCGplayer.' : ' copies to TCGplayer.')],
      href: '#/pricing',
      kbd: ',P',
      behind,
      problem,
      running: live !== null && live.length > 0,
    }
  }

  /* 4b — nothing is ready, and a price is owed. */
  if (needsPrice > 0 || blocked > 0) {
    return {
      key: 'price',
      tone: 'warn',
      icon: 'tag',
      lead: 'Waiting on you',
      say:
        needsPrice > 0
          ? [t(' — price '), n(needsPrice), t(needsPrice === 1 ? ' card.' : ' cards.')]
          : [t(' — set the cut-off price for '), n(blocked), t(blocked === 1 ? ' run.' : ' runs.')],
      href: '#/pricing',
      kbd: ',P',
      behind,
      problem,
      running: live !== null && live.length > 0,
    }
  }

  /* 4c — a file written by hand and never found at TCGplayer (the owner's Q8 ruling). */
  if (unconfirmed !== null && unconfirmed > 0) {
    return {
      key: 'unconfirmed',
      tone: 'warn',
      icon: 'alert',
      lead: 'Waiting on you',
      say: [
        t(' — '),
        n(unconfirmed),
        t(unconfirmed === 1 ? ' copy written, not confirmed at TCGplayer.' : ' copies written, not confirmed at TCGplayer.'),
      ],
      href: '#/pricing',
      kbd: ',P',
      behind,
      problem,
      running: live !== null && live.length > 0,
    }
  }

  /* 5 — the machine has the ball. Not "waiting on you": there is nothing to do but wait, and
         a line that says otherwise is asking for a press that would do nothing. */
  if (live !== null && live.length > 0) {
    const one = live.length === 1 ? live[0]! : null
    const where = one?.box ? `Box ${one.box}` : `${live.length} runs`
    return {
      key: 'working',
      tone: 'live',
      icon: 'play',
      lead: 'Working',
      say: [t(` — ${where} ${live.length === 1 ? 'is' : 'are'} identifying.`)],
      href: '#/runs',
      kbd: ',R',
      behind: [{ figure: null, label: 'Nothing is waiting on you.' }],
      problem,
      running: true,
    }
  }

  /* 6 — photographed and never sent to a run. `states` is store-wide, so this deliberately
         does NOT name a box: `BoxRecord` carries no per-state counts, and attributing a
         store-wide figure to one drawer would be a sentence the data cannot support.

         AND THE DOOR IT OPENS NOW ANSWERS THE SENTENCE. `#/runs?state=captured` puts the
         identify composer up already open, on its default `needed` start — "every card
         waiting to be identified", which is exactly this figure — where a bare `#/runs` leaves
         the operator to open the dialog themselves. Read once on arrival (`Runs.tsx:
         stateInHash`), the way `?run=` already opens a run's own detail; there is no write-back
         of a narrowing into the address, because nothing here links to one yet. */
  const captured = status.states.captured ?? 0
  if (captured > 0) {
    return {
      key: 'captured',
      tone: 'warn',
      icon: 'play',
      lead: 'Waiting on you',
      say: [
        t(' — '),
        n(captured),
        t(captured === 1 ? ' card is photographed and not identified.' : ' cards are photographed and not identified.'),
      ],
      href: '#/runs?state=captured',
      kbd: ',R',
      behind: [],
      problem,
      running: false,
    }
  }

  /* 7 — clear, and only from a complete reading. Every branch that could not read something
         has already returned above, so arriving here means every queue answered. */
  if (runs === null) {
    return unknown(
      'runs-unknown',
      input.runsFailed ? 'the run list did not answer.' : 'the run list is still loading.',
      problem,
    )
  }
  return {
    key: 'clear',
    tone: 'ok',
    icon: null,
    lead: 'Clear',
    say: [t(' — nothing is owed anywhere.')],
    href: null,
    kbd: null,
    behind: [{ figure: null, label: 'Every card photographed has been identified, priced and sent.' }],
    problem,
    running: false,
  }
}
