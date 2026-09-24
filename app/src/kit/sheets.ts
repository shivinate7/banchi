import { useSyncExternalStore } from 'react'
import type { ComponentType } from 'react'

/* ONE WAY TO OPEN A THING FROM WHEREVER IT IS NAMED.
 *
 * A product, an order: every screen that draws one should open it in one press, the same way
 * (the UX review, 2026-09-23, found that a card on one screen could not open the same card on
 * another). A screen never imports another screen to do that. It calls `openSheet(kind, props)`
 * and this registry decides what opens:
 *
 *  - A REGISTERED SHEET, when some module has called `registerSheet(kind, Component)`. The
 *    shell's sheet host reads `useOpenSheet()` and draws the component over the page.
 *  - THE KIND'S OWN ROUTE, when nothing is registered. `product` goes to `#/product?sku=…` and
 *    `order` goes to `#/orders?order=…`. So a link works today, before any sheet exists, and
 *    keeps working if a sheet is removed.
 *
 * A PRODUCT IS OPENED BY SKU, NEVER BY ONE COPY (D212: every copy is fungible). Nothing in this
 * file names a box or a position.
 *
 * TYPED BY A MAP A LATER LANE CAN WIDEN. `SheetProps` is an interface, so a module that adds a
 * new kind declares it with `declare module './kit/sheets' { interface SheetProps { … } }` and
 * gets the same checking the two kinds below get.
 *
 * NOT A COMPONENT FILE. It holds state and one hook, so React Refresh reloading it whole is
 * correct: the registry must not survive an edit to itself. */

/** What each kind of sheet is opened with. Widen it by declaration merging, never by editing
 *  the two entries below. */
export interface SheetProps {
  /** One product, by SKU. `name` is only a caption while the sheet loads. */
  product: { readonly sku: string; readonly name?: string }
  /** One order, by its STORE KEY (`source:number`, `ResolvedLine.order_key`). A bare order
   *  number resolves to nothing on `#/orders`, so it is not what this takes. */
  order: { readonly orderKey: string }
}

export type SheetKind = keyof SheetProps

/** What the shell's sheet host hands every registered sheet besides its own props. `open` goes
 *  false for one leave beat before the host unmounts it, so the sheet's own leave animation runs:
 *  pass it straight to the kit's `Sheet`. Optional, so a sheet that ignores it still types. */
export type SheetHostProps = { readonly onClose: () => void; readonly open?: boolean }

/** The sheet that is open now, as the host draws it. */
export type OpenSheet = {
  readonly [K in SheetKind]: {
    readonly kind: K
    readonly props: SheetProps[K]
    readonly Component: ComponentType<SheetProps[K] & SheetHostProps>
  }
}[SheetKind]

type AnySheet = ComponentType<never>

const registry = new Map<SheetKind, AnySheet>()
let open: OpenSheet | null = null
const listeners = new Set<() => void>()

function emit(): void {
  for (const listener of listeners) listener()
}

/** Where a kind goes when no sheet is registered for it. One place, so a link and a sheet can
 *  never disagree about what "open this product" means. */
const ROUTES: { readonly [K in SheetKind]: (props: SheetProps[K]) => string } = {
  product: ({ sku }) => `#/product?sku=${encodeURIComponent(sku)}`,
  order: ({ orderKey }) => `#/orders?order=${encodeURIComponent(orderKey)}`,
}

/** The address a kind's own page has. A link draws this as its `href`, so a middle-click or
 *  "Open in new tab" still reaches the page when a sheet is registered. */
export function sheetHref<K extends SheetKind>(kind: K, props: SheetProps[K]): string {
  return ROUTES[kind](props)
}

/** Make `kind` open as a sheet. Returns the function that takes the registration back, so a
 *  module that registers in an effect can clean up after itself. */
export function registerSheet<K extends SheetKind>(
  kind: K,
  Component: ComponentType<SheetProps[K] & SheetHostProps>,
): () => void {
  registry.set(kind, Component as AnySheet)
  return () => {
    if (registry.get(kind) === (Component as AnySheet)) registry.delete(kind)
  }
}

/** True when `kind` opens as a sheet rather than as a page. */
export function hasSheet(kind: SheetKind): boolean {
  return registry.has(kind)
}

/** Open `kind`. A registered sheet opens over the page. With none, the kind's own page opens. */
export function openSheet<K extends SheetKind>(kind: K, props: SheetProps[K]): void {
  const Component = registry.get(kind)
  if (Component === undefined) {
    window.location.hash = sheetHref(kind, props)
    return
  }
  open = { kind, props, Component } as unknown as OpenSheet
  emit()
}

/** Close whatever sheet is open. Safe to call when none is. */
export function closeSheet(): void {
  if (open === null) return
  open = null
  emit()
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function snapshot(): OpenSheet | null {
  return open
}

/** The sheet that is open now, or null. The shell's sheet host draws it. */
export function useOpenSheet(): OpenSheet | null {
  return useSyncExternalStore(subscribe, snapshot, snapshot)
}
