## DEBT76 — the walk's card sheet on a phone sells, and no running check proves it

On a phone, a tap on a walk row opens the card in a sheet. The sheet draws `Orders.OrderPickPane`,
the same pane the desk draws. That pane passes `detail` to `CardHero.CardPane`. `detail` holds the
copy rows, and each row carries `OrdersWalkPane.RowAction`, so Mark sold is in the sheet. The gap
this entry first recorded, a sheet with no Mark sold, is fixed in code.

**Outcome at risk:** a change to the sheet or to `OrderPickPane` could drop Mark sold from the
phone sheet, and no check would go red. A picker on a phone would have to close the sheet to mark
a copy sold. Nothing is lost or written wrong.

**Stopgap:** none drawn. The two 390px cases in `app/tests/orders.spec.ts` press `1` with the
sheet open, but both are skipped while `PHONE_SPECS_ON` is false (DEBT77, phone specs off). No
check presses the sheet's own Mark sold button. The sale from the phone sheet is covered only when
`PHONE_SPECS_ON` is true. It is uncovered today.

**Cause, unfixed:** the owner does not use the phone view for walks now, so the phone specs stay
off.

**Closes when:** `PHONE_SPECS_ON` is true and the two 390px cases pass, or the owner drops the
phone walk.
