## D73 — The boot header says the code changed, nothing says the data did, and only one of those is a citation error

**A screen goes stale because nobody is touching it, which is precisely when it has no traffic for a header to ride on — so the boot header's trick cannot be played a second time, and what is owed instead is a re-read at the moment the operator comes back.** Ruled 2026-08-30, after an exhaustive-deps sweep over `app/src` turned up nothing stale on the write path and made it clear the staleness this product actually has arrives from the other device.

**This is not hypothetical and the repo has the receipt.** `app/src/Fulfillment.tsx:537` says it in the first person: *"The list was read once at mount and never again, which is what let him tap Mark sold on a card the other device had already sold — the stale row was still on screen an hour later."* One missing re-read, one wrong sale, no error anywhere, and an hour of a screen quietly lying.

### Two questions wearing one name

`X-Pkmnscan-Boot` answers **did the code change under you**. `server/capture_server.py:302` computes `BOOT_ID` at import, `:308` names the header, `:7986` exposes it across origins, and `:2258` repeats it in `GET /status`. `app/src/server.ts:444` reads it off every response inside `request()` and `:437` hands it to listeners. Two screens consume it. It is a good mechanism and this entry changes none of it.

It cannot answer **did the data change under you**, and the gap is not a missing feature — it is the same fact from the other side. A restart happens *while the operator is working*, so there is traffic in flight for the header to ride. A screen goes stale for exactly the opposite reason: nobody has touched it. There is no traffic to ride, and the only way to manufacture some is the timer the reload notice recorded building, proving and throwing out. **A data-generation header is not a smaller version of the boot header. It is the thing the boot header's own design note explains you cannot have.**

### The sentence that is true of a process and false of a store

`server/capture_server.py:8002` argues the header is honest because *"an idle app learns nothing, and it does not need to: a stale server harms nothing until the next request, and the next request is exactly what carries this."*

That is correct about a process — nothing acts on a boot id. It is **false about a store view**, because the screen is not the only consumer of its own contents. Under D58 a card's number counts the cards in the box, so a screen that has not re-read does not show an old number, it shows a number that now belongs to a **different card**; the operator reads it, counts to it in a drawer, and pulls the wrong card. The harm lands *before* any request, which is the one condition that sentence assumes away. This repo has already measured the identical shape once, in the photo cache at `server/capture_server.py:2314` — *"the operator's reading of that screen is that the delete did not happen, and the next press deletes the card that slid in."* That was fixed with a validator on the response, not with a channel.

**The write is safe; the reading is not.** D58 is explicit that the stored index never moves, so a stale screen's write still lands on the record it names. The residue is entirely a number a human copies off a screen. One correction to the tempting narrow version of this: the phone is not immune either. `app/src/CaptureScreen.tsx:181` holds `UndoTarget = { box; index; label: string | null }` — the server's own rendered label, cached when the capture response landed — and a sale from the Mac in front of those cards renumbers it under D58.

### What is owed, and on which screens

Measured screen by screen against the rig, which is one operator with a phone over the feeder and a Mac on the desk. **Six of the ten routes are structurally immune**: `#/pricing`, `#/orders` and `#/shipping` are written only from the Mac by the operator's own hand, `#/gallery` touches no server, and `#/` is itself the second device — its positions are allocated server-side and `next_index` returns on every response, so its own writes are self-correcting. `#/runs` already polls. `#/fulfillment` is a real third-party writer under D5 and is out of scope here for D31's reason.

**`#/codes` is the sixth, and this entry counted nine against a table of ten until it was measured.** D70 routed it the same day this was written. It writes — `scanCodes`, `buildLot`, `exportCodes` — so it is not excused the way `#/gallery` is. **It is immune by `#/`'s shape, not by D24's pooling**: `app/src/Codes.tsx` renders no slot, the `box/index` it draws is D58's *stored* key behind `photoUrl` (D52), and `server/codes_routes.py` refuses a lot build on a stale claim.

**Two screens are owed something. `#/inventory` is the urgent one** — it is the D58 screen, and a capture from the phone into the box being walked changes the labels the walk draws. `#/review` wants it on next glance.

**The shape is a re-read when the operator returns to a screen, and never a re-render while they are on one — and one screen already does exactly this.** `app/src/Fulfillment.tsx:537` re-reads *"at the moments the list can have moved under it: coming back to it, and finishing a sale. Not a poll — a timer that re-reads while he is reading is a list that reorders under his thumb."* That is D28's argument reached independently from a real incident, and it is the pattern this entry generalises rather than invents. What no screen in the app can do is notice a write landing while the operator sits on it — the hour-long case above.

**Within one browser, "coming back to it" is already free.** `App.tsx` renders `<route.view />` against a table keyed by hash, and all ten views are distinct component types, so every route change unmounts the outgoing screen and every arrival is a full re-read. The gap is not navigation. It is the screen nobody is navigating away from. D28 rules that the list stops moving under a finger already travelling toward a number; that ruling is untouched here and `#/review` is named as prohibited from any automatic mid-session re-render. A notice with a control to press was the alternative and is refused — `docs/DESIGN.md` bans acknowledgements, and the one screen D28 reopened that ban for reopened it on grounds found inside the rule.

### What a signal would cost, banked rather than built

`store/session.py:125` is the single funnel every mutation passes through: exclusive lock, re-read inside it, five JSON files written whole on a clean exit. A counter incremented there covers a capture, a sale, a review answer, a retirement, a divider, an order ingest and a pull without any of them being taught about it, and there is no second door to forget.

**Coalescing is a requirement and not a refinement**, and the number that settles it is already recorded: `docs/GATES.md:884` puts the feeder at a median 623 ms over 84 intervals. Anything that fired per generation would fire twice a second for the length of a box — furniture inside a minute, and worse than silence, because it teaches the operator to ignore the one that matters. A monotonic counter can be compared and coalesced; a random id like `BOOT_ID` cannot.

### Why not a live connection, measured rather than assumed

The owner asked whether this should be less of a static app. It was costed properly rather than declined on precedent, and **the objection is not capacity**: `server/capture_server.py:8583` is a `ThreadingHTTPServer` with one thread per connection and no pool, so a stream starves nothing.

It is the drain. Every verb funnels through `_dispatch`, which counts requests in flight; a stream that sits inside it never leaves, so every save of a watched Python file becomes a 35-second stall, a 40-second supervisor grace, a SIGKILL, and a `check history.jsonl` warning about a store that is fine. D53 restarts the server many times in a working session. There is a second cost that is worse for being quiet: `app/tests/cursor.spec.ts:138` waits for `networkidle`, which an open stream never reaches, and the wait is inside a `.catch` — so the suite would stay green and get roughly three and a half minutes slower with nothing on screen to say why. A WebSocket adds a dependency to the one process that may never need `make venv`, to buy a duplex transport for a simplex problem.

**None of that argues against liveness; it argues against a persistent connection as the first thing to build.** The header-plus-return-to-screen shape contaminates no test, by the mechanism that already makes the boot header safe: a stubbed route sends no header and is therefore silent by construction.

### The citation repair

`ServerReloaded.tsx` opens by citing D53 for the boot id. **D53 does not contain the words `onServerBoot`, `X-Pkmnscan-Boot`, `boot_id`, `BOOT_ID` or `ServerReloaded` — not once.** Checked three ways: a case-insensitive search of this file for "boot" returns five hits, every one `launchctl bootout`, "imported at boot", "will not boot" or "fails to boot"; the identifiers appear in `app/src/`, `server/capture_server.py` and `docs/DEBTS.md` and in no ref's `docs/DECISIONS.md`; and D53 is byte-identical between this worktree and main.

**Seven sites cited D53 for the header or the notice and were re-pointed here**: the reload notice's component and stylesheet (twice in the component), `app/src/server.ts:416` and `:446`, `app/src/types.ts:235`, and the shipping screen. **Four of those seven are gone**: the Banchi rebuild deleted the notice's own two files and the behavior moved into the shell — `app/src/App.tsx`'s server subscription raises a kit toast instead of a component of its own (D94, D95). The rules below survived the deletion intact, which is why this paragraph records the move rather than the entry being rewritten. **Five are correct and are left alone** — `app/src/types.ts:230`, `app/src/App.tsx:787`, `server/capture_server.py:8002`, `server/order_transport.py:542` and `server/tcg_export.py:102` all cite D53 for the watcher, the supervisor or the restart, which are genuinely D53's.

The mechanism is adopted rather than re-argued. Every rule the notice's own header set out stands unchanged: no poll, silence on absence, never on first sight, `role="status"`, expires on its own, hung off `hasChrome` so it never draws on the Fulfiller's view. What changes is which entry it stands on.

### What it costs

- **`docs/DEBTS.md` records that the reload notice has no automated case.** Three were attempted; two passed against a build with the notice rendered unconditionally and were deleted rather than kept, and the third failed outright. Anything built here inherits that difficulty, and the honest move is the one already made — name what is verified and what is not, rather than ship a green row that asserts nothing.
- **A return-to-screen re-read is per screen by construction.** It does not preserve `app/src/server.ts` as the only module that participates, which is a real cost the one-observation-point rule was bought to avoid. Stated rather than denied.
- **`markSold` and `undoSale` take `(box, index)` and carry no aim check.** Only `removeCardInPlace` and the order pull are `capture_id`-aimed. The wire does not refuse a stale press, so nothing here may be argued from the belief that it does.

**D13 is not reopened.** The store, the photographs and the truth stay on this Mac.

**BUILT: the re-read-on-return idiom, on one screen only** — `app/src/Fulfillment.tsx:537`, argued there from the incident above, plus the unmount-on-navigate that makes arrival a re-read everywhere. **RECORDED: this ruling, the two-questions distinction, the citation repair, and the terms a signal would have to meet.** **NEITHER: the generation counter, any signal that reaches a screen nobody is touching, the same idiom on `#/inventory`, and a test for any of it.** The distinction matters because the built half is the half that only helps when the operator was already going to act.

**What would reopen this: a second pair of hands.** Every narrowing above rests on one operator moving between two devices. A real Fulfiller working `#/fulfillment` while the owner sells from `#/inventory` is two people writing at once, and the return-to-screen shape is too slow for it.

---


