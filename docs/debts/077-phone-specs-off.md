## DEBT77 — every phone-width spec is off

By the owner's word, no spec that draws a page below 768px wide runs. That is all of
`app/tests/phone.spec.ts`, the touch-screen block in `app/tests/gallery.spec.ts`, and every
case or width in another spec that sizes the page below 768. `PHONE_SPECS_ON` in
`app/tests/phoneSwitch.ts` is the one switch. No test is deleted.

**Outcome at risk:** a phone layout break goes unseen. A thumb target under 40px, a sideways
scroll at 390 or a sheet that no longer rises from the bottom passes CI and reaches the owner's
phone.

**Stopgap:** none. The phone views are still drawn by the same CSS. Only the readers are off.

**Cause, unfixed:** the owner does not use the phone view now, and the phone cases cost suite
time.

**Closes when:** the owner turns phone back on. The fix is one edit, `PHONE_SPECS_ON = true`.
