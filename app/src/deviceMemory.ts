/**
 * WHAT THIS BROWSER REMEMBERS ABOUT ITSELF — the whole of it, in one file.
 *
 * D27 permits `localStorage` for facts about THIS MACHINE and nothing else, and CLAUDE.md's
 * ban is about the other thing entirely: nothing about a card, a position or the inventory
 * goes in browser storage, because D13 puts that one truth on the Mac so two devices cannot
 * disagree about where a card is. Neither rule has moved. What moved is that Banchi's shell
 * has preferences of its own, and they are the same KIND of fact `useCamera.ts` already
 * stores — meaningless on the Fulfiller's laptop, wrong if shared, and about no card.
 *
 * THE THEME IS THE CLEAREST CASE. A person who chose dark chose it for the room they are
 * sitting in. Putting it on the server would make the owner's phone in the garage follow the
 * laptop in the office, and putting it in `sessionStorage` would ask them again every tab.
 * The rail's width is the same fact about the same screen.
 *
 * WHY THEY ARE IN THIS FILE RATHER THAN AT THEIR CALL SITES. `app/eslint.config.js` bans the
 * store rather than the key, because a selector cannot read a key passed as a const — so the
 * exception has to be a FILE, and a file the reviewer can read whole. `useCamera.ts` is the
 * other one and it holds the remembered camera and the photo rotation. Adding a device-local
 * key means adding it here, where the argument is, in front of whoever is reviewing the diff.
 *
 * THIS COMMENT CLAIMED THOSE TWO FILES HELD EVERY `localStorage` CALL IN THE APP, and that
 * stopped being true on 2026-09-03. `Orders.tsx` holds a key — `banchi.orders.last-check`,
 * when THIS device last checked TCGplayer — at two call sites carrying an inline disable that
 * argues for it, which the owner ruled on. So the shape is two exempt FILES plus one argued
 * call site, and the roster lives in `CLAUDE.md` where `make docs-audit`'s `storage keys` row
 * reconciles it against this directory in both directions. A comment that counts is a comment
 * that goes stale; the count is checked there, and this one deliberately does not make it.
 *
 * THE ORDER FETCH FILTER (D114) CAME HERE RATHER THAN TO ITS CALL SITE, which is the shape
 * the lint rule's own message asks for and the opposite of what `last-check` did. That key
 * predates this argument being written down; a new one goes where the reviewer is already
 * looking.
 *
 * EVERY ACCESS IS WRAPPED. Private windows, cleared site data and browsers set to block
 * storage all throw on the accessor itself, and a preference is never worth a blank screen.
 */

const THEME_KEY = 'banchi.theme'
const RAIL_KEY = 'banchi.rail'

export type Theme = 'light' | 'dark'

/** The theme the operator CHOSE, or null where they have not — which is not the same as
 *  light. A null here is what lets the shell keep following the system. */
export function storedTheme(): Theme | null {
  try {
    const stored = localStorage.getItem(THEME_KEY)
    return stored === 'light' || stored === 'dark' ? stored : null
  } catch {
    return null
  }
}

export function rememberTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_KEY, theme)
  } catch {
    /* storage unavailable — the theme still applies for this session */
  }
}

/** Whether the nav is collapsed to the rail, or null where this browser has no opinion. */
export function storedRail(): boolean | null {
  try {
    const stored = localStorage.getItem(RAIL_KEY)
    if (stored === 'rail') return true
    if (stored === 'wide') return false
    return null
  } catch {
    return null
  }
}

export function rememberRail(rail: boolean): void {
  try {
    localStorage.setItem(RAIL_KEY, rail ? 'rail' : 'wide')
  } catch {
    /* storage unavailable — the rail still moves for this session */
  }
}

/* ------------------------------------------------------------------ the order fetch filter */

/**
 * HOW THIS DEVICE NARROWS ITS ORDER FETCH, and why that is a fact about the machine.
 *
 * D91 made `POST /orders/fetch` refuse a call that names no statuses, on an argument
 * `server/order_transport.py` makes at length: TCGplayer never published the status
 * vocabulary, so a guess that drops an order is an envelope that never ships. The owner then
 * ruled out D91's two-press flow, and `Orders.tsx` answered the requirement by echoing back
 * every status the free preview returned — nothing dropped, and nothing narrowed either. This
 * key is the operator's own answer in place of that echo (D114).
 *
 * IT IS A HABIT, NOT A RECORD. "I do not want to look at completed orders" is a statement
 * about how the person at this screen works, the same kind of fact as the remembered camera
 * and the theme; it names no order, no card, no position and no SKU, and losing it costs one
 * press of a control that is on screen. The ledger stays the one truth about what is on the
 * store, which is the whole of what D13's ban protects.
 *
 * ONE KEY FOR BOTH TOGGLES, BECAUSE THEY ARE ONE FACT. `statuses` is which of the window's
 * orders are worth a detail call; `skipKnown` is whether the ones the ledger already holds at
 * that status are worth asking about again. Both answer "what should this press bother with",
 * both are ticked in the same panel, and splitting them would put two rows in `CLAUDE.md`'s
 * roster for one habit.
 *
 * THE STRINGS ARE THE WIRE'S OWN, KEPT VERBATIM. What is written here is exactly what the
 * preview answered, never folded and never mapped, because that is the one comparison the
 * transport does — `status.strip() in wanted` — and a fold on this side would be the first
 * step toward the vocabulary that module refuses to have. A remembered string that a later
 * window does not return is therefore a real possibility, and the screen SAYS SO rather than
 * quietly dropping it.
 *
 * NULL IS NOT AN EMPTY LIST, AND IT IS NOT "UNANSWERED" EITHER — that is what `asked` is for.
 * `statuses: null` means "every status this window holds", which stays the value a confirmed
 * device usually carries: a stored LIST would silently drop a status TCGplayer adds next month,
 * which is the exact drop D91 exists to prevent. An empty list means they ticked everything off,
 * and the screen refuses the press rather than sending a body the wire rejects with a code the
 * operator cannot act on.
 *
 * `asked` IS WHETHER A HUMAN HAS SEEN THE LIST, AND THE FIRST PRESS WAITS FOR IT. The owner
 * decided this on 2026-09-06 against a measurement: 69 of the 83 open orders on their store are
 * ones TCGplayer had already shipped, those orders hold 31 physical copies, and three
 * Ready-to-Ship lines read `short` while the cards sat in boxes — because `resolve_all` serves
 * oldest-first out of one pool and a delivered order is older than a live one. A default of
 * "everything" reproduces that on every device where nobody opens the control.
 *
 * THE ALTERNATIVE WAS A CODED DEFAULT AND IT IS NOT AVAILABLE. "Everything except the shipped
 * ones" needs this file to know that `Shipped - In Transit` means shipped, which is the
 * vocabulary `server/order_transport.py` refuses to have and which would swallow a `Refunded`
 * TCGplayer adds later. So a human is asked, once, in front of the real list — and never again.
 * This is NOT D91's two-press flow, which the owner ruled out: that asked on every press.
 */
const ORDER_FILTER_KEY = 'banchi.orders.fetch-filter'

/** The buyer list's own standing view — status, sort, whether an unresolved SKU is folded
 *  out — added to this SAME document rather than a new key. The owner's ruling for the six
 *  capture values above is the same habit here: "the view I work the list in" is one fact a
 *  person sets and clears together, and `app/src/orderView.ts:DEFAULT_ORDER_VIEW` is what a
 *  device that has never touched these controls gets — every row shown, newest first. */
export type OrderView = {
  readonly status: string | null
  readonly sort: 'newest' | 'oldest'
  readonly hideUnknown: boolean
}

/** What this device narrows the order fetch to. `statuses: null` is every status the window
 *  holds; `asked` is whether a human has ever been shown that list. `view` is the buyer
 *  list's sort/filter, above. */
export type OrderFetchFilter = {
  readonly statuses: readonly string[] | null
  readonly skipKnown: boolean
  readonly asked: boolean
  readonly view: OrderView
}

const DEFAULT_VIEW: OrderView = { status: null, sort: 'newest', hideUnknown: false }

/** A device that has never been asked. Every status — and, as of `D193`,
 *  skipping what the ledger already holds by default: the ordinary press is an all-statuses,
 *  skip-known append, and a device that never opens the picker gets that press rather than a
 *  slower one nobody chose. The picker still opens from its own "Only these statuses…" control. */
const UNASKED: OrderFetchFilter = { statuses: null, skipKnown: true, asked: false, view: DEFAULT_VIEW }

function parsedView(raw: unknown): OrderView {
  if (typeof raw !== 'object' || raw === null) return DEFAULT_VIEW
  const status = (raw as { status?: unknown }).status
  const sort = (raw as { sort?: unknown }).sort
  const hideUnknown = (raw as { hideUnknown?: unknown }).hideUnknown
  return {
    status: typeof status === 'string' && status.trim() !== '' ? status : null,
    sort: sort === 'oldest' ? 'oldest' : 'newest',
    hideUnknown: hideUnknown === true,
  }
}

export function storedOrderFilter(): OrderFetchFilter {
  try {
    const raw = localStorage.getItem(ORDER_FILTER_KEY)
    if (raw === null) return UNASKED
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return UNASKED
    const list = (parsed as { statuses?: unknown }).statuses
    /* Deduped and stripped on the way out, so a hand-edited value cannot make the fetch body
       something the wire refuses for a reason the operator cannot see. */
    const statuses = Array.isArray(list)
      ? [...new Set(list.filter((one): one is string => typeof one === 'string').map((one) => one.trim()))].filter(
          (one) => one !== '',
        )
      : null
    return {
      statuses,
      /* Defaults to true. A stored value written before `D193` carries
         `skipKnown: false` from the old UNASKED default, and a device that had genuinely opted
         out reads back the same way — the two are indistinguishable on disk, and the ordinary
         press is the safer of the two to default to. */
      skipKnown: (parsed as { skipKnown?: unknown }).skipKnown !== false,
      asked: (parsed as { asked?: unknown }).asked === true,
      /* Absent on every document written before this field existed — reads as `DEFAULT_VIEW`,
         the same "show everything" a fresh device gets, so an old value never narrows a list
         it never chose to narrow. */
      view: parsedView((parsed as { view?: unknown }).view),
    }
  } catch {
    /* Private mode, blocked storage, or a half-written value. UNASKED, which means the press
       stops and shows the list — the safe direction, because the unsafe one imports orders that
       were delivered a month ago and lets them hold copies a live order needs. A browser that
       refuses storage asks every time, which is the honest consequence of refusing storage. */
    return UNASKED
  }
}

export function rememberOrderFilter(filter: OrderFetchFilter): void {
  try {
    localStorage.setItem(
      ORDER_FILTER_KEY,
      JSON.stringify({
        statuses: filter.statuses === null ? null : [...filter.statuses],
        skipKnown: filter.skipKnown,
        asked: filter.asked,
        view: filter.view,
      }),
    )
  } catch {
    /* Quota or a blocked origin. The choice still holds for this tab; only the next visit is
       asked again. */
  }
}

/* ------------------------------------------------------------- the inventory walk's habits */

/**
 * TWO FACTS ABOUT HOW THE PERSON AT THIS SCREEN WALKS THE BOXES (D132), and neither is a fact
 * about a card. Whether sold rows are worth scrolling past is the same kind of statement as
 * "I do not want to look at completed orders" above; which boxes this browser opened lately
 * is `banchi.orders.last-check`'s kind — when THIS device did something, so a list can be
 * ordered by it. Both were put to the owner on 2026-09-10 and both were ruled device-local:
 * the phone in the garage and the laptop at the desk are looking for different boxes.
 *
 * SOLD IS HIDDEN UNTIL SOMEBODY SAYS OTHERWISE. The absent key reads as `true`, which is the
 * owner's default and the one that costs a press only when a sold row is what you came for.
 */
const HIDE_SOLD_KEY = 'banchi.inventory.hide-sold'

/** Whether the walk and the copies list fold departed copies away. Default true. */
export function storedHideSold(): boolean {
  try {
    return localStorage.getItem(HIDE_SOLD_KEY) !== 'show'
  } catch {
    return true
  }
}

export function rememberHideSold(hide: boolean): void {
  try {
    localStorage.setItem(HIDE_SOLD_KEY, hide ? 'hide' : 'show')
  } catch {
    /* storage unavailable — the choice still holds for this tab */
  }
}

/**
 * WHEN THIS BROWSER LAST PUT ITS HAND ON EACH BOX, by box number, as an ISO stamp. Two lists
 * sort on it, newest first, and a box this browser has never reached for sorts after every box
 * it has. Capped so a store with hundreds of boxes cannot grow the value without bound: the
 * fifty most recent are kept, which is more boxes than either list shows without scrolling.
 *
 * A PAGE LOAD IS NOT AN OPENING. `BoxBrowse` touches a box from a press on the rail and from a
 * walk-to, never from the `?box=` landing — otherwise every visit would reorder the rail.
 * `CaptureScreen` touches one when the operator PICKS it, and deliberately not when a capture
 * lands: a capture fires once per card, and a `localStorage` write per photograph would put
 * this file on the feeder's hot path to record a fact that has not changed since the pick.
 *
 * TWO SCREENS WRITE IT, AND THAT IS WHY THE KEY IS NOT CALLED `banchi.inventory.box-recency`
 * ANY MORE. It was, from D132 until the capture screen started reading it, and by then the
 * name said which SCREEN had written the fact instead of what the fact is — which is about the
 * operator's hand and not about either list. Renaming it abandons what a browser holds, the
 * rule D27's second amendment set and the reason a read-time fallback was declined there; the
 * cost is one sitting of the fallback order (fullest, then number) until the first box is
 * opened or captured into, and the two lists rebuild it from the same presses that built it
 * before.
 *
 * ONE FACT, NOT TWO, AND THAT IS A RULING RATHER THAN AN ECONOMY (D142).
 * Capture could have kept a recency store of its own, and the argument against is that there
 * is one operator with one hand: photographing into box 7 and then walking to `#/inventory`
 * is the same person still thinking about box 7, and a rail that opened on some other drawer
 * would be answering a question nobody asked. The shared store is what makes the second screen
 * agree with the first without either knowing about the other.
 */
const BOX_RECENCY_KEY = 'banchi.box-recency'
const BOX_RECENCY_KEEP = 50

export function storedBoxRecency(): ReadonlyMap<number, string> {
  try {
    const raw = localStorage.getItem(BOX_RECENCY_KEY)
    if (raw === null) return new Map()
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return new Map()
    const out = new Map<number, string>()
    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      const box = Number.parseInt(key, 10)
      if (Number.isInteger(box) && box > 0 && typeof value === 'string') out.set(box, value)
    }
    return out
  } catch {
    return new Map()
  }
}

/** Record that this browser opened `box` now; returns the map as it stands after. */
export function touchBox(box: number, at: Date = new Date()): ReadonlyMap<number, string> {
  const held = new Map(storedBoxRecency())
  held.set(box, at.toISOString())
  const kept = [...held.entries()]
    .sort((a, b) => (a[1] < b[1] ? 1 : a[1] > b[1] ? -1 : 0))
    .slice(0, BOX_RECENCY_KEEP)
  const next = new Map(kept)
  try {
    localStorage.setItem(BOX_RECENCY_KEY, JSON.stringify(Object.fromEntries(next)))
  } catch {
    /* storage unavailable — the order still holds for this tab */
  }
  return next
}

/* ------------------------------------------------------- the capture screen's last setup */

/**
 * WHAT THE OPERATOR HAD SET UP AT THE LENS THE LAST TIME THEY WERE HERE (D142).
 *
 * THE OWNER ASKED FOR IT IN THESE WORDS: *"ideally let it save my last used on capture on all
 * settings ... so the game i picked, camera i picked, all stay saved in some sorta session
 * history"*. The camera already did — `useCamera.ts` has held `banchi.capture.deviceId` and
 * `banchi.capture.rotation` in `localStorage` since before D27 generalised the carve-out — so
 * what this adds is the rest of the setup, under the same prefix, on the same clock.
 *
 * THIS IS AN AMENDMENT TO D27 AND NOT AN EXCEPTION TO IT. That entry put these values in
 * `sessionStorage` on the argument that *"a new tab is a new shift and closing the browser ends
 * one"*, and the operator's own report is that the premise is wrong: a shift ends when they stop
 * feeding cards, which is hours after the browser closed and has nothing to do with either. What
 * D27 was actually protecting is one value and it is NOT in here — see `captureId` in
 * `CaptureScreen.tsx`, which stays in `sessionStorage` with the reason on it.
 *
 * ONE KEY FOR SIX VALUES, BECAUSE IT IS ONE HABIT. `banchi.orders.fetch-filter` above makes this
 * argument for its two fields and it holds harder here: "the setup I work at" is a single thing
 * the operator sets up once and clears in one press, six rows in `CLAUDE.md`'s roster would be
 * six rows for one fact, and the clear is one `removeItem` rather than six that can half-fail.
 *
 * NONE OF IT IS A FACT ABOUT A CARD, which is the test D13 and D27 actually set. A box NUMBER is
 * the closest thing here to one and it is not one either: it says which drawer this operator is
 * working out of, not where any card IS. The store stays the one truth about that, every value
 * here is resent to the server on every capture, and a browser that has never seen this key
 * renders the screen it always rendered.
 *
 * A STORED VALUE IS INPUT, NOT STATE, and this file validates only what it can: the SHAPE.
 * Whether the game still exists, whether the rarity is still authored, whether the box is still
 * open — those are questions for the registry and the store, and `CaptureScreen.tsx` asks all
 * three on arrival. A reader here that guessed at them would be a second, weaker copy of a check
 * the screen already has to make.
 */
const CAPTURE_SETUP_KEY = 'banchi.capture.setup'

/** The six choices the capture screen remembers between sittings. `setHint` is `''` rather than
 *  null because the control is a text field and empty is what it holds; the other five carry the
 *  screen's own "nothing claimed" value. */
export type CaptureSetup = {
  readonly box: number | null
  /** WHICH DRAWER THAT NUMBER MEANT WHEN IT WAS PICKED (D145), so the restore can tell the box
   *  the operator left from a different box wearing its number today. `null` where the pick
   *  predates this field, or where the store had no id to give. Never rendered; the screen
   *  compares it and draws the sentence that comparison produces. */
  readonly bid: number | null
  readonly game: string | null
  readonly setHint: string
  readonly finish: readonly string[]
  readonly rarityClaim: readonly string[]
  readonly product: string | null
}

/** Nothing chosen — what a browser that has never opened this screen holds, and what the
 *  screen's own clear writes. `game: null` is read by the screen as "take the registry's
 *  default", which is what a first load does. */
export const NO_CAPTURE_SETUP: CaptureSetup = {
  box: null,
  bid: null,
  game: null,
  setHint: '',
  finish: [],
  rarityClaim: [],
  product: null,
}

/** Digits, a safe integer, 1 or higher — the Box entry's own rule exactly, and it has to be: the
 *  box decides which physical drawer a photograph is filed into. `'1e3'` and `'3.7'` are both
 *  things `Number` would read as a different, entirely valid box that nobody typed, and JSON
 *  will hand back `1e3` as the number 1000 without either spelling surviving to be noticed. */
function readBox(value: unknown): number | null {
  if (typeof value !== 'number') return null
  return Number.isSafeInteger(value) && value >= 1 ? value : null
}

/** A non-empty trimmed string, or null. The two claims that are single-valued — `game` and
 *  `product` — are stored as the registry's own keys and checked against it when they land. */
function readWord(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

/** A list of strings, members that are not strings dropped rather than the whole list — the
 *  member-wise salvage `CaptureScreen.tsx` already applies to a claim whose game renamed a
 *  rarity under it. A claim the operator really made about the stack survives an edit to one
 *  member of it. */
function readList(value: unknown): readonly string[] {
  if (!Array.isArray(value)) return []
  return value.filter((member): member is string => typeof member === 'string')
}

export function storedCaptureSetup(): CaptureSetup {
  try {
    const raw = localStorage.getItem(CAPTURE_SETUP_KEY)
    if (raw === null) return NO_CAPTURE_SETUP
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return NO_CAPTURE_SETUP
    const held = parsed as Record<string, unknown>
    return {
      box: readBox(held.box),
      /* THE SAME SHAPE RULE AS THE BOX, and nothing more (D145). Whether this id still names
         the drawer at that number is exactly the question `CaptureScreen.tsx` asks the store,
         and this file's own rule is that a stored value is INPUT: a reader here that tried to
         answer it would be a second, weaker copy of the check the screen has to make anyway.
         A missing key reads `null`, which the screen has a named arm for. */
      bid: readBox(held.bid),
      game: readWord(held.game),
      /* Unvalidated beyond its being a string, and that is a decision rather than a gap: a
         length cap or a set-code pattern here would make a RESTORED hint stricter than a typed
         one, so a hint the operator legitimately entered could come back changed or missing. */
      setHint: typeof held.setHint === 'string' ? held.setHint : '',
      finish: readList(held.finish),
      rarityClaim: readList(held.rarityClaim),
      product: readWord(held.product),
    }
  } catch {
    /* Private mode, blocked storage, or a half-written value. Nothing chosen, which is the
       screen this operator saw before any of this existed — and every field is one press. */
    return NO_CAPTURE_SETUP
  }
}

export function rememberCaptureSetup(setup: CaptureSetup): void {
  try {
    localStorage.setItem(
      CAPTURE_SETUP_KEY,
      JSON.stringify({
        box: setup.box,
        bid: setup.bid,
        game: setup.game,
        setHint: setup.setHint,
        finish: [...setup.finish],
        rarityClaim: [...setup.rarityClaim],
        product: setup.product,
      }),
    )
  } catch {
    /* Quota or a blocked origin. The setup still holds for this tab; only the next visit
       starts from nothing, which is where every visit started until 2026-09-11. */
  }
}

/** Forget it outright, rather than writing `NO_CAPTURE_SETUP` over it. The absent key and the
 *  empty setup read identically on the way back in, and a key that is gone is the honest record
 *  of a clear — nothing here should leave a browser holding a document that says the operator
 *  chose nothing, which is not a thing anybody chose. */
export function forgetCaptureSetup(): void {
  try {
    localStorage.removeItem(CAPTURE_SETUP_KEY)
  } catch {
    /* storage unavailable — the clear still happened on screen, which is the part that was
       pressed for. */
  }
}

/* ------------------------------------------------------- how loud the spend confirm gets */

/**
 * THE FIGURE ABOVE WHICH THE IDENTIFY CONFIRM SAYS SOMETHING EXTRA — AND IT IS A NOTICE, NEVER
 * A CEILING.
 *
 * THE OWNER'S RULING, 2026-09-12, is the whole shape of this key: *"Give me settings if I can
 * have them, but if I want to run everything, then I get to run everything."* So this raises a
 * sentence and a one-press way to stop being asked; it never disables the spend button, never
 * hides it, and there is no number at which a press is refused. A ceiling that refused
 * "everything" would be this app deciding how much of their own store the operator may read —
 * which `server/pipeline_routes.py:do_pipeline_preflight` refuses in writing on the same ground.
 *
 * WHY IT IS DEVICE-LOCAL AND NOT IN THE STORE. It is a statement about how loud this screen
 * should be, in the same family as the theme and the order fetch filter above: it names no card,
 * no position, no SKU and no run, and losing it costs one press of a control that is on screen.
 * The figures it is compared against are the server's — `RunPreflightTotal.estimate_usd`, lifted
 * out of the command's own preflight — and no arithmetic about money happens on this side.
 *
 * THE DEFAULT IS $1.00 AND IT IS DERIVED, NOT PICKED. `identify/cost.py:INPUT_PER_MTOK` is
 * $0.50/MTok — Haiku 4.5's $1 input, halved by the Batch API's 50% discount — and a card at
 * `max_edge` 1200 measures 2,641 input tokens, so a card costs about $0.00132 and a dollar is
 * about 757 cards. Measured against the real store the same day: that is larger than every
 * drawer on it but box 3 (887 cards), and roughly a quarter of a full store re-read (2,535
 * cards, about $3.35). So an ordinary drawer press never trips it and a store-wide one always
 * does, which is exactly the line worth a second sentence.
 *
 * THE 2,641 FIGURE IS A CORRECTION AND THE OLD ONE IS NAMED SO IT DOES NOT COME BACK: ~2,420
 * tokens a card divided one run's input tokens by its 723 cards when 191 of those were cache
 * hits. A cache hit sends no image, so it is not a divisor — it is a card that cost nothing.
 */
const SPEND_NOTICE_KEY = 'banchi.runs.spend-notice'

/** What this device asks about above, in dollars. See the block above for the derivation. */
export const SPEND_NOTICE_DEFAULT = 1

export function storedSpendNotice(): number {
  try {
    const raw = localStorage.getItem(SPEND_NOTICE_KEY)
    if (raw === null) return SPEND_NOTICE_DEFAULT
    const parsed = Number(raw)
    /* A stored value is INPUT, and this file validates what it can: a figure that is not a
       positive finite number is not a dollar amount. Zero is refused along with the rest —
       a notice at $0.00 fires on every press including the free ones, which reads as a
       malfunction rather than as a setting, and the honest way to never be asked is a figure
       above the biggest press this store can make. */
    return Number.isFinite(parsed) && parsed > 0 ? parsed : SPEND_NOTICE_DEFAULT
  } catch {
    /* Private mode, blocked storage, or a half-written value. The default, which is the
       loudest of the honest answers: being asked about a dollar is cheap, and a browser that
       refuses storage is asked again next visit. */
    return SPEND_NOTICE_DEFAULT
  }
}

export function rememberSpendNotice(dollars: number): void {
  if (!Number.isFinite(dollars) || dollars <= 0) return
  try {
    localStorage.setItem(SPEND_NOTICE_KEY, String(dollars))
  } catch {
    /* Quota or a blocked origin. The figure still holds for this tab, which is the press that
       was made — only the next visit is asked again. */
  }
}
