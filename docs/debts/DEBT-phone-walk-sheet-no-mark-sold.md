## DEBT-phone-walk-sheet-no-mark-sold — the walk's card sheet on a phone has no Mark sold

On a phone, a tap on a walk row opens the card in a sheet. Since the card pane became the head,
the band and the photograph alone, the sheet holds no copies and no Mark sold. The press is on
the copy row in the walk list, under the sheet's scrim. The number keys (`1` to `9`) that mark a
copy sold do not exist on a phone.

**Outcome at risk:** a picker on a phone who opens the card to check it must close the sheet
before they can mark it sold. Nothing is lost or written wrong. The cost is one extra press on
one form factor.

**Stopgap:** none drawn. The two 390px cases in `app/tests/orders.spec.ts` press `1` with the
sheet open, so the sale itself stays covered.

**Cause, unfixed:** the owner does not use the phone view for walks now, so the sheet was left
as the pane. A fix would give the sheet its own Mark sold on the current pick's copies.

**Closes when:** the owner starts using the phone for walks.
