import type { OrderLineWire, OrderRow } from './types'

/* THE GROSS MATH OF `#/revenue`, MOVED UNCHANGED OUT OF `Revenue.tsx` so a test can call it
 * (D214: gross only, Canceled orders left out, never profit). `position.ts` and `money.ts`
 * state why a pure function does not sit beside a component: React Refresh. */

/** The one word this screen treats as "not a sale" — folded the way `is_terminal_status`
 *  folds its own vocabulary, but for exactly one status rather than that whole terminal set. */
function isCanceled(status: string | null): boolean {
  return (status ?? '').trim().toLowerCase() === 'canceled'
}

/** `"None"` IS TCGPLAYER'S OWN LITERAL STRING FOR A PRODUCT WITH NO RARITY
 *  (`pipeline/games.py`'s own `rarities_not_claimed` entry, both Riftbound and One Piece):
 *  73 sealed products and 12 rarity-less tokens in Riftbound alone carry it verbatim in the
 *  `Rarity` column, never blank. Read as `null` here so it never draws as though "None" were
 *  a real rarity a card was identified under — the same normalisation `pipeline/games.py`
 *  already names for exactly this string. */
function realRarity(raw: string | null): string | null {
  return raw === 'None' ? null : raw
}

/** One line, with its order's placed-at date and a real number for `unit_price` — the one
 *  arithmetic step this screen performs, over a string the wire sends because money crosses
 *  it as text (`OrderLineWire`'s own comment). A line with no usable DATE cannot be placed on
 *  the sparkline at all and is left out, counted once in `dropped`. A line with no usable
 *  PRICE is kept — `priceKnown` says so, and `salesOf`'s own header explains why. */
export type Sale = {
  /** The order's identity (`OrderRow.key`) — never shown, only counted and grouped by. */
  readonly order: string
  /** The order's label (`OrderRow.number`) — what the drill-down shows a person. */
  readonly orderNumber: string
  readonly at: Date
  readonly name: string
  /** True where `name` fell back to the line's own SKU because the feed sent no name —
   *  the fact `nameIsSku` at the render site draws in mono rather than guessing from the
   *  string's own shape. */
  readonly nameIsSku: boolean
  readonly sku: string
  readonly quantity: number
  /** `0` where `priceKnown` is false — never read on its own without checking that flag. */
  readonly unitPrice: number
  /** `false` where TCGplayer's own feed carried no usable price on this line
   *  (D298, finding 1: `unit_price: ""`, not `null`, is how the feed says
   *  so). */
  readonly priceKnown: boolean
  /** `0` where `priceKnown` is false. */
  readonly gross: number
  readonly condition: string | null
  readonly rarity: string | null
  /** `OrderLineWire.kind` verbatim — `'sealed'` is the one value this screen reads on its own
   *  (item 5, item 2 of the review round): a sealed line never has a rarity, and it is never
   *  drawn as though one is simply unread. */
  readonly kind: string | null
  /** THE `skus` TABLE'S OWN PRODUCT/SET TEXT FOR THIS SKU (`OrderLineWire.product_line`/
   *  `set_name`), never the feed's own line fields — carried through so a short display name
   *  can be built off a long TCGplayer product title (item 3, review round) without this
   *  screen inventing product taxonomy of its own. `null` where the SKU is not in that table. */
  readonly productLine: string | null
  readonly setName: string | null
}

/** `true` where the OPERATOR closed this line as never shipping — a refund or a
 *  cancellation, `store/orders.CLOSE_NOT_SHIPPING`'s own words for `not_shipping` — during fulfilment,
 *  matched by SKU against the same order's `OrderLineProgress` list (D225,
 *  `docs/specs/sales-plan.md` §2). `closed_reason` rides on every order's `progress`
 *  already; this screen was simply never reading it. NOT THE MARKETPLACE'S WORD: the value
 *  is recorded by a person during fulfilment, so a line can be a real refund the operator
 *  never got around to closing, and this can only ever undercount, never overcount. */
function isClosedNotShipping(order: OrderRow, sku: string): boolean {
  return order.progress.some((p) => p.sku === sku && p.closed_reason === 'not_shipping')
}

/** `null` for a `unit_price` this screen cannot read as a real number: TCGplayer's `null`
 *  ("said nothing") and its `""` (D298, finding 1) read the same way — both
 *  mean the feed carried no price on this line, never a guessed one. `Number('')` is `0` in
 *  JavaScript, which is the bug this guards: an empty string must never reach `Number()`. */
function parsePrice(raw: string | null): number | null {
  if (raw === null) return null
  const trimmed = raw.trim()
  if (trimmed === '') return null
  const n = Number(trimmed)
  return Number.isFinite(n) ? n : null
}

export function salesOf(
  orders: readonly OrderRow[],
): {
  readonly sales: Sale[]
  readonly dropped: number
  readonly refundExcluded: number
  readonly canceledOrders: number
} {
  const sales: Sale[] = []
  let dropped = 0
  let refundExcluded = 0
  let canceledOrders = 0
  for (const order of orders) {
    if (isCanceled(order.status)) {
      canceledOrders += 1
      continue
    }
    if (order.placed_at === null) {
      dropped += order.lines.length
      continue
    }
    const at = new Date(order.placed_at)
    if (Number.isNaN(at.getTime())) {
      dropped += order.lines.length
      continue
    }
    for (const line of order.lines as readonly OrderLineWire[]) {
      if (isClosedNotShipping(order, line.sku)) {
        refundExcluded += 1
        continue
      }
      const price = parsePrice(line.unit_price)
      const priceKnown = price !== null
      sales.push({
        order: order.key,
        orderNumber: order.number,
        at,
        name: line.name ?? line.sku,
        nameIsSku: line.name === null,
        sku: line.sku,
        quantity: line.quantity,
        unitPrice: priceKnown ? price : 0,
        priceKnown,
        gross: priceKnown ? price * line.quantity : 0,
        condition: line.condition,
        rarity: realRarity(line.rarity),
        kind: line.kind,
        productLine: line.product_line ?? null,
        setName: line.set_name ?? null,
      })
    }
  }
  return { sales, dropped, refundExcluded, canceledOrders }
}

export function sum(sales: readonly Sale[]): number {
  return sales.reduce((total, sale) => total + sale.gross, 0)
}
