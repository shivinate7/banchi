import { OrdersHub } from './Orders'
import './Shipping.css'

/* `#/shipping` — the Orders hub with the Ship stage selected. The stage itself lives in
   `OrdersShipStage.tsx`, which `Orders.tsx` imports; this file only points the route at the hub,
   so the two routes render one screen without importing each other. */
export function Shipping() {
  return <OrdersHub stage="ship" />
}
