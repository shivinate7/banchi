## DEBT-single-reds-on-main — three design-check tests went red once on main, with no cause read

**What.** Three design-check tests went red once each on main in the window. No later run went red on the same test. Their causes are unread.

- **`boxmap.spec.ts:365`** (`grip drag: at 820 wide, a drag held at the bottom edge autoscrolls to a box below the fold`). Job `design-check (8)`, run 2544. The message: `expect(locator).toBeVisible()` timed out at 15 s, with the element not found.
- **`capture-section.spec.ts:1072`** (`Background Match holds its height while the switch state loads`). Job `design-check (10)`, run 2632. The message: `the row changed height when the state arrived`. This is the shape the stability floor exists to catch, so it may be a real shift.
- **`section-ruler.spec.ts:342`** (`the tick number under or next to the pin is hidden, and the chip sits mid-track`). Job `design-check (11)`, run 2813. The message: `chip centred on the track`.
- **Measured.** 3 of the 100 most recent completed main check runs (window run numbers 2489 to 3148). Each was red on the first attempt and stayed red on main until a later push.
- **Cause.** Cause unread for all three. Not read: the traces. Not done: a local run of any of the three.
- **Owner.** shivinate7. **Fix by.** 2026-12-01 (D308, a deadline date is allowed).
- **Outcome at risk.** Each may be a real defect that the next push hid. A drag that autoscrolls wrongly, a row that moves as its state loads, and an off-centre chip each cost the operator a wrong read.
- **Closes when.** Each cause is written here, from its trace, and each test passes on main for the window. A real defect moves to its own record.
