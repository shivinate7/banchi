import type { DecisionsDocument, PricingSku } from './types'

/* WHAT `emit` WOULD REFUSE THIS RUN FOR, computed here so the pricing screen can say it
 * without a round trip. D54.
 *
 * THIS IS A SECOND IMPLEMENTATION OF `pipeline/decisions.py:blocking`, AND THAT IS THE
 * OWNER'S CHOICE RATHER THAN AN ACCIDENT. The screen autosaves `inventory/prices.json` on
 * every commit, so a server-computed answer would lag the keystroke that satisfies it — and
 * the whole value of the line is that it settles the moment you answer. The cost is drift.
 *
 * NOTHING AUDITS THIS TODAY — `docs/DEBTS.md` names it. This header claimed an `emit
 * readiness` docs-audit row and a `make readiness-agreement` target until 2026-09-02, and
 * neither has ever existed. What does exist is the roster on `GET /pipeline/pricing`, which
 * asks the Python that actually refuses, so a chip and this line can disagree and the chip is
 * the one that is right.
 *
 * SO THIS FILE IS SHAPED TO BE AUDITED, even though nothing does yet. `OWED_REASONS` is a
 * flat literal a parser can read, every reason is constructed by `owed` below, and nothing
 * else in the app spells one of these strings.
 *
 * WHAT IT ANSWERS, EXACTLY: "is pricing answered". NEVER "will emit succeed". `cli/cmd_emit.py`
 * also refuses on cards routed to a queue that are not in one on disk, an empty catalog, a
 * disposition naming a SKU outside the batch, a suppressed per-game report, and an
 * unparseable document — none of which this file can see, and one of which (the unparseable
 * document) it cannot even detect, because a screen holding a malformed document in memory
 * has already parsed it. The sentence on screen says so.
 *
 * IT MAY NEVER GROW TO READ `overrides`, A HOLD, OR THE FLOOR. `blocking()` reads none of
 * them, and a client that consulted one would be claiming a refusal Python does not make —
 * which is worse than missing one, because it is a run the operator never presses. The
 * fixture pins the sharpest case: a hand-priced override does NOT satisfy the sub-threshold
 * gate, and `pipeline/decisions.py:332` is where that is decided.
 */

/** The literal `pipeline/decisions.py:FLOOR_CHOICE` compares against, with a bare `==` and no
 *  trim or case fold. Nothing else in this app may spell it: a value derived from a button's
 *  label is a `MalformedDecisions` waiting for the next join. */
export const FLOOR_CHOICE = 'floor'

/** The key `pipeline/decisions.py:FLAT_KEY` looks for. Only its PRESENCE is checked there,
 *  and the value goes through `Decimal(str(v))` — so it travels as a string, which is also
 *  what `to_payload` round-trips. */
export const FLAT_KEY = 'flat'

/** Every reason `emit` can refuse a run for that this screen can see.
 *
 *  EXACTLY TWO, and it agrees with `pipeline/decisions.py:blocking`'s two `reasons.append(...)`
 *  calls today. NOTHING CHECKS THAT, and this comment said it did: it called the count "the
 *  auditable fact" and claimed "the audit row asserts the two vocabularies match in both
 *  directions" until 2026-09-05, while `scripts/docs-audit.py` had never mentioned this file
 *  or this constant at all. A third reason in Python without a third here is a refusal this
 *  screen cannot show, and today only a person reading both files would find it. */
export const OWED_REASONS = ['sub_threshold_unset', 'no_market_data_unanswered'] as const

export type OwedReason = (typeof OWED_REASONS)[number]

/** Human labels. PROSE, and deliberately NOT audited — a rule about wording would be the
 *  audit taking a view on English, which is the boundary `check_withhold_reasons` already
 *  draws for the hold vocabulary. */
export const OWED_LABELS: Record<OwedReason, string> = {
  sub_threshold_unset: "the store's sub-threshold policy (null in the file)",
  no_market_data_unanswered: 'a price for every card with no market value',
}

export type Owed = { reason: OwedReason; count: number }

/**
 * What pricing still owes, in `blocking()`'s own order — which its docstring calls "the order
 * a human would want to read it".
 *
 * `subThresholdSkus` is derived from the pricing table's `bucket`, which `cli/cmd_join.py`
 * writes from the same set `cli/resolve.py:sub_threshold_skus` returns. Same set, no fetch.
 */
export function owed(
  doc: DecisionsDocument | null,
  subThresholdSkus: readonly string[],
): Owed[] {
  const out: Owed[] = []

  // RULE 1 — `pipeline/decisions.py:332`. Note what it does NOT consult: `overrides`. Pricing
  // all 108 of a box's sub-threshold SKUs by hand still leaves `emit` refusing, which is the
  // measured state of two runs on disk and the reason the strip exists at all.
  if ((doc?.sub_threshold ?? null) === null && subThresholdSkus.length > 0) {
    out.push({ reason: 'sub_threshold_unset', count: subThresholdSkus.length })
  }

  // RULE 2 — `pipeline/decisions.py:325`, the `unanswered` property. THE DOCUMENT'S MAP, NOT
  // THE TABLE'S BUCKET: Python counts entries in `no_market_data` whose value is null, so a
  // SKU the operator never answered at all is invisible to it. Reading the bucket instead
  // would report a refusal `emit` does not make — the direction this file must never err in.
  const unanswered = Object.values(doc?.no_market_data ?? {}).filter((v) => v === null)
  if (unanswered.length > 0) {
    out.push({ reason: 'no_market_data_unanswered', count: unanswered.length })
  }

  return out
}

/** The sub-threshold SKUs of a pricing table — the argument `owed` wants. */
export function subThresholdSkus(skus: readonly PricingSku[]): string[] {
  return skus.filter((s) => s.bucket === 'sub_threshold').map((s) => s.sku)
}
