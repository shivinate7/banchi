# UI research: the three proposals against established practice

**STATUS: RECORDED, NOT BUILT.** Nothing here is implemented. This is the evidence pass over
`docs/specs/ui-redesign-options.md`, run 2026-08-24 at the owner's instruction — *"surf the web
too to confirm the way you're designing is sound with others that try to solve this problem,
ensure you're using established best practices while also not being afraid of breaking out of
the mold."*

**Method.** Twelve agents: eight researched a domain of prior art each with live web search and
full-page reads, three then tried to REFUTE one proposal apiece using the pooled corpus, and one
synthesised. 482 tool calls. Domains: three-pane layouts, data-annotation tools, radiology PACS,
keyboard-first triage, command palettes, tethered capture, pipeline dashboards, and
density/single-surface anti-patterns. Every URL below was visited by the agent that cites it.

**The headline: B and C are refuted, A survives only as a skeleton.** The Line is not brave and
untested — it is the position the field occupied and vacated (Jenkins Blue Ocean, deprecated
July 2026; Dagster beat Airflow by moving *further* toward objects). The Slab dies on an absence:
the corpus was searched for a tool with more than one object type that navigates by typed line
alone, and there is none. The Rig's skeleton is the best-evidenced structure in the corpus and
"The Rig as written" still fails, because it specifies no resting state, no per-task
configuration, no persistence rule and no reset.

**Claims verified against this tree before recording**: five max-widths (`CaptureScreen.css:16`
1400, `Inventory.css:43` 1240, `Gallery.css:10` 900, `Fulfillment.css:41` 720,
`ReviewQueue.css:85` 688); `ReviewQueue.css:93` `--photo-cap: 48vh`; `App.tsx:254`
`CHORD_MS = 1500`; `RunPanel.tsx:438` `<details className="run-panel">`; `RunPanel.tsx:68`
`STEPS` holding exactly identify / join / emit / reconcile.

**A defect found while verifying, which the research did not catch.** `ReviewQueue.css:47`
states "THE CAP IN FORCE IS 60vh" while line 93 declares `--photo-cap: 48vh`. That comment was
written to retire an earlier 38vh/34vh drift and warns in its own words against "a comment
reasoning toward a number the file does not use ... Worse than no comment, because it reads as
the current thinking." It has become the thing it warns about. Fixing it is free and unrelated
to any proposal.

---

# PKMNSCAN UI: final design recommendation

*Synthesis of five research domains, three adversarial passes, and a verification read of the live tree.*

---

## 0. Three corrections to the brief before anything else

These matter because two of them change the arithmetic.

1. **There are five max-widths, not three.** Verified: `CaptureScreen.css:16` → 1400px, `Inventory.css:43` → 1240px, `Gallery.css:10` → 900px, `Fulfillment.css:41` → 720px, `ReviewQueue.css:85` → 688px. Every one was chosen alone and argued alone.

2. **The capture screen already has a portrait frame variant.** `CaptureScreen.css:985` ships a portrait pair for rotation 90/270, added after the first feeder session because "the landscape frame spent two thirds of itself on letterbox." The 16:9 waste is real only at rotation 0. The *coequal* half of the criticism stands; the aspect half is half-fixed.

3. **The review photo is not merely small — it is capped, and the cap is what the empty column buys.** `ReviewQueue.css` declares `--photo-cap: 48vh` = **432px** at 900px viewport. A 63×88mm card (aspect 0.716) at 432px tall draws **309px wide**: 133,488px², **10.3% of a 1440×900 viewport**, for the one thing that screen exists to show. The cap exists because everything stacks in one 688px column and the sentence plus first candidate must stay visible. **The 752px of empty width is not idle waste sitting next to a badly-sized photo. It is the direct cause of the photo being that size.** That reframing is the single most useful finding in this whole exercise.

---

## 1. Which proposal survives

**None as written. The recommendation is A's skeleton, run as four declared postures, with B's counts demoted onto objects and C's field demoted to a component.**

Call it **one skeleton, four protocols**.

### Why A's skeleton and not B's or C's

The evidence is one-sided on the *unit of navigation*. Jenkins Blue Ocean was the purest stage-first UX ever shipped and is **deprecated July 2026** ([jenkins.io/doc/book/blueocean](https://www.jenkins.io/doc/book/blueocean/)); the stage graph survived only as a view inside a job object. Dagster beat Airflow by moving *further toward objects* ([dagster.io/blog/dagster-airflow](https://dagster.io/blog/dagster-airflow)). GitHub Actions ships zero counts in navigation. Shopify demoted stage tabs off its highest-traffic fulfilment screen to search-first ([help.shopify.com](https://help.shopify.com/en/manual/shopify-admin/productivity-tools/searching-filtering-views)). No tool with multiple object types navigates by stage alone. **B is not brave and untested; it is the position the field occupied and vacated.** D31 already reached the same answer from use: *"it's basically find a card in a box-based system if anything."*

B additionally fails on its own facts. Verified against `RunPanel.tsx:68`, the pipeline has **four** steps — identify, join, emit, reconcile — and B's seven stops omit `join`, the step whose own note reads *"Writes the queues and the pricing questions."* B renders ANSWER and PRICE as stops while hiding the command that produces both, and has nowhere to put `join --bypass`, which cleared 209 of box 2's 256 queue candidates. B's counts also carry three denominators — cards (`STATES`), run directories (`_phase`, which explicitly permits parallel runs across boxes), and SKU copies (`Listing.pushed/staged/live`) — which destroys the one claim B is built on. And D7's fungibility means a card is at several stops at once.

C dies on an absence: the research was searched for a counterexample and found none. Superhuman — the most keyboard-extreme product surveyed — writes it out in its own palette guide: *"Of course, your typical UI elements — such as buttons, dropdown menus, etc. — should continue to exist!"* ([blog.superhuman.com](https://blog.superhuman.com/how-to-build-a-remarkable-command-palette/)). Prodigy has no in-page nav because it has one dataset per server process and selection happens at a terminal — the exact boundary C crosses. And C's arithmetic is fatal on its own terms: deleting a 45px nav strip to install a 40px command line recovers **5px of 900**, 0.56%, while the measured waste is 752px of width and 4,018px of scroll.

### Why "as written" fails for A too

The owner's objection is correct and A has no answer, because A specifies **no resting state, no per-posture configuration, no persistence rule, and no reset**. Radiology — the field that invented fixed layouts — says exactly this in its own words: where the protocol library is thin, *"the viewer defaults to a layout that satisfies no one"* ([blog.medicai.io](https://blog.medicai.io/en/radiology-hanging-protocols/)). That is the owner's sentence, confirmed by people who pay for it.

The remedy is not fewer zones. It is **more protocols**, exactly as OHIF ships them — scored against what you opened, with a guaranteed `default` when nothing matches ([docs.ohif.org](https://docs.ohif.org/platform/services/data/hangingprotocolservice/)) — and as Blender ships Workspaces "geared towards particular tasks." A frame with three zones and no presets is 54 reachable configurations, several unusable. A frame with four named postures is four.

### The four postures, with numbers at 1440×900

| | RAIL | STAGE | DOCK |
|---|---|---|---|
| **SHOOT** `#/capture` | **absent** | two panes, **mode-dependent ratio**, draggable divider | 320–400px claim bar (already `--side-w`) |
| **ANSWER** `#/answer` | 280px — **last ten decisions** | split: photograph ∥ candidates | **gone** |
| **BROWSE** `#/inventory` | 280px — boxes + state beads | box walk → section → card | 340px — facts, copies, neighbours, re-shoot |
| **RUN** `#/box/N/run` | mini 56px | four steps, preflight, money gate, verbatim stdout, downloads | gone |

Ticker: one line, bottom, **never collapses** — VS Code's Status Bar is one of six permanent zones ([code.visualstudio.com/docs/configure/custom-layout](https://code.visualstudio.com/docs/configure/custom-layout)).

**`#/fulfillment` keeps its own frame and its own route.** This is not negotiable and "one frame for the entire app" must be withdrawn outright: a 280px rail of box rows with state beads fails DESIGN.md's 20px-per-text-node floor and its 44×44/12px-apart tap floor simultaneously; a key-labeled dock fails "his screens are touch and show none"; a rail that navigates at all is a route *out* of the view, forbidden outright; and "box", "queue", "import" fail the banned-word list. That is four of nine rows currently green in `app/tests/fulfillment.spec.ts`. D31 makes the Fulfiller downstream, which permits an owner-only frame — it does not permit rendering the owner's shell around his view.

---

## 2. What the research vindicates

**The no-overlay rule.** Figma shipped floating panels in UI3 beta and reversed them before GA: panels *"cramped the canvas"*, designs *"peek out from behind them"*, and the deciding finding was that floating panels **slowed down power users spending many hours daily** ([figma.com/blog/our-approach-to-designing-ui3](https://www.figma.com/blog/our-approach-to-designing-ui3/)). Blender has enforced non-overlap for 30 years. Someone else ran this experiment at enormous scale and lost.

**`[` and `]` as bare zone toggles.** Linear ships this character-for-character: *"the `]` and `[` shortcuts open and close the sidebar and details pane"* ([linear.app/changelog/2026-04-30-releases](https://linear.app/changelog/2026-04-30-releases)). Leave `Cmd+[` / `Cmd+]` alone for history.

**Hash addressing everywhere.** Linear ships full history inside a one-page shell. It costs zero pixels and the repo depends on it structurally — route-is-not-a-feature, D33's poll against a run directory that survives a tab close, `scripts/views.txt`, `make screenshot`.

**One key per candidate, no modifier, no confirm.** Prodigy binds bare digits 1–9 and sustains 830 annotations in ~40 min ≈ 2.9s/item ([explosion.ai](https://explosion.ai/blog/prodigy-annotation-tool-active-learning)). Label Studio requires `Ctrl+Enter` and is nobody's throughput reference. D28 rejected requiring a modifier; that was right.

**One card at a time, photo first.** RSNA measured stack mode at **3.2–5.7× faster than tile mode (P=.0002), 0 errors vs 2** ([pubs.rsna.org](https://pubs.rsna.org/doi/10.1148/radiology.203.1.9122394)). DESIGN.md arrived at this independently. Defend it against any future "grid of pending cards" request.

**Group-answering a homogeneous queue raises quality, not just speed.** MorphoCluster: macro precision **0.949 vs 0.738** — 21 points *up* — for cluster annotation against one-at-a-time ([PMC7308937](https://pmc.ncbi.nlm.nih.gov/articles/PMC7308937/)). D29 currently justifies itself on tap count and hedges hard on safety. The hedge is aimed at the wrong risk: showing a human sixteen photographs at once makes them *compare*, which one-at-a-time never asks.

**Expensive-first sorting is the intervention that matters.** Active worklist reordering cut turnaround **43.7%**; badge/flag systems that only decorated the same list cut it **7.6%** ([pubs.rsna.org/ryai.2020200024](https://pubs.rsna.org/doi/full/10.1148/ryai.2020200024)). `store/queues.py:sort_key` already does the winning half.

**Grouping physically uniform stacks so nothing is adjusted between captures.** OCLC's cross-case conclusion; Bancroft cut high-end capture costs *"by 80% and more"* with it. This is the whole justification for pre-sorted stacks and per-stack claims, and it is the strongest external validation the capture model gets.

**D32's crop-in-memory rule matches the standard verbatim.** FADGI 6.3: *"We recommend the entire object be scanned, without cropping. A small border should be visible."* Opus archives raw images first so treatment can be redone "with different parameters and new algorithms." D32 reasoned to the same place independently.

**D33's two-step, no-typing money gate.** NN/g reserves confirmation for *"actions… costing large amounts of money"* and for the irreversible. This product gates exactly one action and nothing else, which is the part most products get wrong.

---

## 3. What must change

### 3.1 The worklist leaves the review flow. (largest single win)

47 entries at ~71px/row is **~3,318px of the 4,018px** — 82% of the scroll, in one edit. Across a session pass that is **188,846px**, and NN/g's 2018 eye-tracking (120 participants, 130k+ fixations) puts **74% of viewing time inside the first 2,160px** ([nngroup.com/articles/scrolling-and-attention](https://www.nngroup.com/articles/scrolling-and-attention/)). 4,018px is 1.86× past that line.

No high-throughput annotation tool puts the pending queue beside the item. Prodigy shows one card and the **last ten decisions**, editable, with `history_size` defaulting to `batch_size` = 10 ([prodi.gy/docs/api-web-app](https://prodi.gy/docs/api-web-app)). Label Studio physically separates Data Manager from Label Stream. Zendesk removes the queue at work time so agents *"spend their mental energy on solving tickets rather than combing through the queue"* ([zendesk.com/blog/play-button](https://www.zendesk.com/blog/play-button/)).

**What sits beside the card is what is BEHIND you, not ahead of you.** Ahead is anxiety and scroll; behind is the safety net that makes one-key-no-confirm honest.

The price-band hierarchy is not lost. `sort_key` already sorts expensive-first server-side and auto-advance follows it — the operator benefits from the sort without seeing it. Keep a **price-band strip** in the rail's mini state (how many big ones remain) at ~56px instead of 3,318px.

### 3.2 The photograph and the candidates go side by side; the 48vh cap retires.

Arithmetic at 1440×900, ANSWER posture: rail 280 + page padding 32 + gap 24 = 336px chrome, stage **1,104px**, content:chrome **3.29:1**. Available height 900 − 46 nav − 16 pad − 45 head − 24 ticker = **769px**.

Photograph pane 607px, card drawn at **551×769** = 423,719px², **32.7% of the viewport** — **3.17× today's area**. Candidate pane 473px, content measure 441px ≈ 61 mono characters: `Near Mint Reverse Holofoil` (26 chars) plus price on one line, name and set on a second. Nine candidates × ~56px = 504px, comfortably inside 769.

**The tuned 656px measure is preserved where it was tuned — for the finding sentence,** which sits full-width in the head above the split. It was never tuned for candidate rows.

**And the candidates must NOT go in a 340px dock.** That is the Outlook/Thunderbird middle-pane scrunch: Microsoft's own answer to a clamped list column is *"that's what the design was intended to be"* with the remedy being to hide a different zone ([learn.microsoft.com](https://learn.microsoft.com/en-us/answers/questions/4673671/how-to-adjust-narrow-three-column-widths-in-outloo)); Thunderbird bug 213945 ran 2003→~2023 on the same complaint ([bugzilla.mozilla.org/213945](https://bugzilla.mozilla.org/show_bug.cgi?id=213945)).

### 3.3 A 1:1 sheen inset, pinned in the review stage.

Both governing digitization standards require this class of judgment at native resolution. FADGI: evaluation *"shall be conducted while viewing the images at a 1 to 1 pixel ratio or 100% magnification"* ([digitizationguidelines.gov](https://www.digitizationguidelines.gov/guidelines/FADGI%20Technical%20Guidelines%20for%20Digitizing%20Cultural%20Heritage%20Materials_3rd%20Edition_05092023.pdf)). Metamorfoze 2.22: *"viewed at 100% size on a calibrated monitor… in a dim environment without daylight"* ([metamorfoze.nl](https://www.metamorfoze.nl/sites/default/files/documents/Preservation%20Imaging%20Guidelines%20English%202.0,%20April%202025.pdf)).

This is not academic here. The human on this screen is the appeal court for a detector that was **wrong on 230 of 544 cards (42%)** with the owner supplying ground truth, and **19 of 40 frames disagreed with themselves** between max-edge 900 and 1200 — direct evidence that sheen does not survive downscaling. Asking a person to adjudicate foil from a 5.8:1 fit-to-box render is asking them to judge on evidence the standards say has been destroyed. A 400×300 native-pixel inset costs 400×300 CSS px and is prefetched with the next card, which D28 already mandates.

**This is the rare change that raises accuracy, kills whitespace, and adds no keystroke.**

### 3.4 The pipeline leaves the `<details>`.

Verified: `RunPanel.tsx:438` is `<details className="run-panel" open={live > 0}>`. NN/g names this in one sentence — *"Never hide essential information in collapsed panels"* — prices the interaction at five accumulating substeps, warns collapsed content *"may be missed altogether"*, and lists the explicit do-not-use case as content users need on most visits ([nngroup.com/articles/accordions-on-desktop](https://www.nngroup.com/articles/accordions-on-desktop/)).

The radiology interruption literature prices the departure it forces: **+2.3 min per interruption**, gaze off the subject for 30 s afterward, sternal-fracture detection collapsing **60% → 12.5%** ([PMC5833804](https://pmc.ncbi.nlm.nih.gov/articles/PMC5833804/)). D33's fold argument — ~250px, reached once a box — proves the panel belongs *on the box*. It does not prove it belongs *collapsed*: a thing reached once per box is reached every box, which is the definition of the primary task.

Give it the RUN posture, addressed, with the real four steps and the two-step money gate intact.

### 3.5 One declared measure, and the 150px rule enforced.

Five max-widths means the same control lands at a different x on every route, which forfeits the largest measured expert-speed effect available: CommandMaps found a spatially-stable, maximally-flattened surface at **1.57s vs 2.11s (Ribbon) vs 2.40s (menus)** — 25% and 34% faster, **F₂,₃₄ = 114.0, p < .001**, with an **error rate one-tenth** of both and **no novice penalty** ([commandMap-finalCamera.pdf](https://www.csse.canterbury.ac.nz/andrew.cockburn/papers/commandMap-finalCamera.pdf)). Experienced users pointed at commands on a **blank** Ribbon with a median 92px error.

Note the form of the fix. Radiology does not achieve consistency with one width for everything — it makes the width a **declared property of the task type**, identical every time. Three widths is not the defect; three *undeclared* widths is.

DESIGN.md's own 150px first-content rule is currently enforced by nothing, and it says so. Assert it in Playwright across all four owner routes.

### 3.6 Capture: the panes stop being coequal.

No capture UI surveyed shows both images at equal size. Capture One CH's Slipstream gives live view the large pane while shooting and **flips** in Delete/Retake mode — *"the captured image is on the left, thumbnails on the right"* — with the divider draggable ([teamworkphoto.com](https://teamworkphoto.com/online-store/phase-one-system/phase-one-software/capture-one-cultural-heritage/)). Sony's Remote window has **no** captured-image area at all. Lightroom Classic has **no live view at all** and a large population shoots tethered on it daily.

Also: **stop swapping a full-size image at 1.6 Hz.** Capture One ships `Auto Select New Capture: Never` specifically for *"slower hardware and high paced shooting"*, and an `Immediate` mode that shows a pixelated camera thumbnail rather than wait ([imagealchemist.net](https://imagealchemist.net/capture-one-tethering-in-depth/)). This repo has already paid twice for full-size work at burst pace — Gate B's 33MB-per-press canvas leak and the idle-scheduled encoder.

### 3.7 The keyboard corrections.

- `CHORD_MS = 1500` (verified, `App.tsx:254`) → **1000ms**. Vim's `timeoutlen` and which-key's default are both 1000; practitioners recommend 500. At a 623ms cadence, 1500ms is **2.4 card-cycles of swallowed input**, and the code's own comment says *"an armed leader eats the next keystroke."*
- **Split on `tab` / `shift-tab`, not `\`.** Superhuman shipped this exact feature and chose positional keys, because pane movement is spatial and has no verb to be a mnemonic for.
- **Fix the `g` collision.** `g` = game picker on capture, `g` = GROUP bulk-answer on review. The other three collisions (`c`, `r`, `s`) are memory load only; `g` is the doorway to a write across N cards. Move the group offer to the leader or the palette.
- **Ship `?`, context-scoped.** lazygit exposes 144 keybindings through help scoped to the *focused panel*. A flat sheet is the "alphabetically sorted, equally useless" failure. Costs zero pixels at rest.
- **Zone keys inert on `#/capture` while a trigger is armed.** KLM: one mental operator M = 1.2s = **193% of a 623ms cycle**. "Which zone am I in?" does not fit inside a feeder cycle.

### 3.8 Undo goes to depth 10 and loses its timer — on review only.

At 2–6s per card, a 20-second window is ~4 cards wide but reaches only the newest, and the realistic error is noticed on card N+3. Prodigy runs depth-10 with no expiry. `Queue.upsert`'s refusal already stands for everything outside the window, so widening from 1 to 10 is **a change of bound, not of rule**. Mark-sold keeps its 20s — there the operator is holding the card and feedback is immediate.

### 3.9 Counts come from one server-derived endpoint, and render `—` when null.

GitLab's own tracker records this failing at scale: *"Both the old navigation and new navigation update some counts, but not all… implemented ad hoc"* ([gitlab.com/-/issues/429678](https://gitlab.com/gitlab-org/gitlab/-/issues/429678)). One `GET /pipeline/counts` over the store, refreshed on mutation and on a poll, **no client-side accumulators**. The codebase already documents the null rendering in `_queue_depth`: *"A count that is wrong in the direction of 'there is more to do' is worse here than no count."* Honour it in the rail.

### 3.10 An age term in `sort_key`. (not a UI change — do it anyway)

The 47 residual entries are all `no_catalog_row`. Cards with no catalog row have no price, and `sort_key` sorts unpriced **last**. They will never rise. The chest X-ray simulation over ~1,000,000 images documents exactly this: prioritized ordering pushed the worst case to **1,178 min vs 890 under plain FIFO** until a maximum-waiting-time escalation was added ([PMC8128725](https://pmc.ncbi.nlm.nih.gov/articles/PMC8128725/)). At 40 boxes this is ~400 permanently starved entries. **No review-screen redesign fixes this and none should be asked to.**

---

## 4. Where to deliberately break convention

The owner asked not to be trapped by best practice. Here is where best practice is wrong *for this tool*, with the argument for each.

**① Hide chrome on desktop. NN/g says don't; do it anyway.**
NN/g's objection is discovery cost across a population with varying familiarity. There is one operator and he wrote the bindings. VS Code ships Zen Mode at professional scale. **Condition:** the cycle rests at *mini*, never *gone* — mini satisfies NN/g's "simple and reliable reveal" requirement and gone does not. Reach gone only by explicit act.

**② Live view is not load-bearing during a run — collapse it to a strip.**
Every tethering convention assumes seconds per item and a human in the framing loop. This rig has neither: the feeder places every card in the same spot and a motion trigger fires. Lightroom Classic ships tethering with **no live view at all**. Internet Archive's Scribe shows only the captured pages. Live view here is a *setup* instrument, not a *shooting* instrument. This is the correct application of A's `[` collapse and it recovers ~485px on the busiest screen.

**③ Stop verifying writes by looking at an image.**
No tethering product verifies transfer by eye — Capture One owns the counter because the camera cannot be asked for one, and ships a Next Capture Backup Tool; Sony's remedy is "Dest. + Camera". At **623ms — 5,778 cards/hour, 7.2× Scribe's 800-pages-per-hour target and 46× FADGI 2-star book scanning** — no human verifies anything. The panel's stated job ("a failed write is visible") is the counter's job being done badly by an image. Replace with a counter, a gap check and a flash; the existing "85 records at indices 1..85, zero gaps, 85 distinct capture_ids" check is already the right instrument. **Real per-card verification moves to a contact sheet.**

**④ Put a physical grey patch in every frame. No consumer software does this; every digitization standard requires it.**
Metamorfoze mandates a workflow target within 5cm of the original in every preservation master, *"to compare the stability of the image performance over a series of images or scans."* RBGE mounts a fixed colour chart and scale bar on the backboard. Two runs have now concluded "systematic sheen under the rig's lighting" — 30% at Gate B, 42% at box 2 — from **indirect** evidence. A grey patch taped to the tray turns that into a per-card number computed locally and free, and makes D3's stated re-enable condition ("a rig that measures better") a thing you can *test* rather than assert. It survives D32's crop because the crop is in-memory. **Cost: one printed card. This is the highest leverage-per-dollar item in the entire synthesis and it is not a UI change at all.**

**⑤ Restate "minimize whitespace" as "minimize travel", and refuse the first version.**
Prodigy caps its card at 675px on a 1440px screen and is the reference tool for annotation speed. Empty space beside a small card is not itself a defect. But *our* item is a photograph being judged for sheen — CVAT's genre, not Prodigy's — so the 752px goes to **the card and the 1:1 inset**, not to more UI and not to a worklist. Space that shortens the eye's path from photo to candidate row earns its keep; space that lengthens it does not. Reject "fill the width with more UI"; accept "fill the width with more card."

**⑥ Consider loosening D29 past its double condition, on quality grounds.**
D29 requires one shared reason **and** one shared candidate. MorphoCluster is evidence that the hedge points the wrong way: cluster annotation *raised* macro precision to 0.949 from 0.738. Box 2's 230 disagreements are 230 different catalog rows and D29 cannot touch them. `--bypass` has since made this less urgent, so this is flagged as an argument the owner should hear, **not** a change to make silently — it reopens D4 and needs a ruling.

**⑦ Do not spend more pixels on key hints.**
Grossman et al. built the strongest possible permanent visual hint — blinking hotkey, hotkey following the cursor, menu replaced by the hotkey — and it came **last of five conditions at 50%, below the 57.1% do-nothing control**. What worked was manipulating *cost*: disabled-menu 72.8% against a 28.9% control ([tovigrossman.com](https://www.tovigrossman.com/papers/chi%202007%20hotkeys.pdf)). Honest caveat: their mappings were deliberately non-mnemonic and ours are mnemonic, so the effect size will not transfer whole — but the direction will. Keep chips on rarely-visited screens; drop them on the overlearned hot loops (capture at 623ms, review digits); add `?`. This breaks *DESIGN.md's own* "Every choice shows its key" and therefore needs an owner ruling.

**⑧ The Fulfiller does not get a vote — and that means the frame is owner-only, stated out loud.**
D31 is right that he is downstream. The break is admitting the consequence rather than papering it: this product will have **two** navigational paradigms, and that is correct, because one of them is a floor built for a retired non-technical user with a full battery of assertions behind it.

---

## 5. The strongest remaining argument against this direction

**The frame fixes none of the four measured defects, and two of its three zones already exist.**

Verified: `CaptureScreen.css:151` is already `grid-template-columns: var(--side-w) minmax(0, 1fr)`. `BoxBrowse.css:137` is already `minmax(300px, 380px) minmax(0, 1fr)`. **The 240px header and the y=482 photo happened inside rail|stage layouts.** And `BoxBrowse.css`'s own header records what actually fixed the 240px: deleting a 48px title, a 68px lede and a 52px mode switch — DESIGN.md's page-chrome budget, which is orthogonal to zoning. Likewise the 4,018px of scroll is a *stacking* decision inside a 688px column, not a missing frame.

So the honest case is: every item in §3.1–3.10 is achievable without a frame, and the frame's remaining claim rests on CommandMaps — a result measured on **command selection in Microsoft Word**, not on a four-screen app whose one user already knows where everything is. The 25–34% may not transfer at all.

Two second-order versions of the same objection:

- **The frame's own navigation zone destroys the frame's justification at scale.** `BoxBrowse.css`'s box strip wraps rather than scrolls past ~a dozen boxes, and its comment says why: *"a horizontal scroller hides the boxes it cannot show."* At 40 boxes, 32px rows are 1,280px in a 900px viewport, so the rail scrolls, its items move, and the stable-coordinate property that is the whole case is gone. **Mitigation:** the rail becomes search-first past ~15 boxes and rests at mini, carrying one number — the review depth, the only rail datum that is ever urgent. That is VS Code's Activity Bar precedent.

- **A four-posture frame multiplies the ways to ship something unreachable, and this repo's own record says nothing on the commit path would catch it.** GATES.md step 7b: three screens missing from the ROUTES table while harness, lint, typecheck and docs-audit were all green, and only `make design-check` — deliberately off the commit path — failed, 16 of 30. A frame rewrite is that risk at four times the surface.

**The correct response is sequencing, not argument.** Do §3.1–3.3 *as* the ANSWER posture — the frame's first instance, on the route where the measured harm is largest — measure it, and extend only if the measurement holds. Do not let the frame collect credit for repairs it does not perform.

---

## 6. Ranked, actionable

| # | Change | Evidence forcing it | Size |
|---|---|---|---|
| **1** | Worklist out of the review flow → rail as last-ten-decisions + a price-band strip | −3,318px of 4,018px per card (82%); ×47 = 188,846px/session; Prodigy, Zendesk, Label Studio all agree | M |
| **2** | Photo ∥ candidates split; retire `--photo-cap: 48vh`; sentence keeps its 656px measure in the head | photo 309×432 → 551×769, **3.17× area**, 10.3% → 32.7% of viewport | M |
| **3** | **1:1 sheen inset**, ~400×300 native px, prefetched with the next card | FADGI + Metamorfoze both require 1:1; detection wrong on 42% of 544; 19/40 self-disagreed across downscales | S |
| **4** | Grey patch on the tray, in every frame | Metamorfoze 3.2; turns "systematic sheen" from inference into a number; makes D3's re-enable condition testable | **XS — one printed card** |
| **5** | Pipeline out of `<details>` into an addressed RUN posture, real four steps | NN/g accordions; +2.3min/interruption, detection 60%→12.5%; route-is-not-a-feature at one remove | M |
| **6** | Age term in `store/queues.py:sort_key` | 47 `no_catalog_row` sort last forever; worst case 1,178 vs 890 min until escalation added | **XS** |
| **7** | Capture: mode-dependent pane ratio + draggable divider; throttle the stored-capture swap to motion-stop or a thumbnail | Slipstream flips its panes; `Auto Select New Capture: Never`; two prior burst-pace defects already paid for | S |
| **8** | Review undo → depth 10, no timer (mark-sold keeps 20s) | 2–6s/card makes a 20s depth-1 window unreachable; Prodigy `history_size` = 10 | S |
| **9** | `CHORD_MS` 1500→1000; split on `tab`/`shift-tab`; fix the `g` collision; ship context-scoped `?`; zone keys inert while armed | vim/which-key = 1000; KLM M = 193% of a 623ms cycle; `g` arms an N-card write | S |
| **10** | One `GET /pipeline/counts`; stage beads on box rows; ticker renders the run directory with a ratio, elapsed, and a stop | GitLab 429678; NN/g >10s needs percent-done + interrupt; D33 runs outlive the server | M |
| **11** | Declare one measure; enforce the 150px first-content rule in Playwright across all four owner routes | five max-widths verified; CommandMaps 25–34%, F₂,₃₄=114.0; DESIGN.md admits nothing enforces it | S |
| **12** | **Contact sheet** — a whole box at thumbnail density, gaps and edge-touching crops flagged | FADGI makes all-frames thumbnail review the *first* QC act; box 2's 47 residuals were 38 blank + 9 wrong numbers found **after** $0.71 was spent | M |
| **13** | Formalise the frame: four postures, one global persisted zone triple (D27 `sessionStorage`), one reset key | OHIF's guaranteed `default`; Blender Workspaces; VS Code "remembers the layout… across your sessions" + "Reset View Locations" | L |
| **14** | Subject line as a **component** — takes a name (`2/17`, a card name, a SKU, `box 2`), aliased, context-weighted, writes the hash, summoned by one key, hosted in the rail | Notational Velocity; Chrome's omnibox merged *inputs* and kept tabs, back/forward and bookmarks | M |

### Acceptance tests, since this repo writes numbers rather than adjectives

- First content row **≤150px** from viewport top, all four owner routes.
- Per-card scroll on `#/answer` **≤900px** (one viewport). Currently 4,018.
- Answer keystroke → next card painted **<100ms** (Superhuman's published budget; the prefetch is already D28's).
- Photograph area **≥25% of viewport** on `#/answer`. Currently 10.3%.
- Zone x-coordinates **identical across every posture in which a zone is present**. This is the frame's own central claim, made checkable — and if it fails, item 13 has not earned its cost.

### One thing to withdraw from the record

"One frame for the entire app" is false by construction and must not survive into a decision entry. The frame is **four owner routes**; `#/fulfillment` keeps its own frame, its own route, and its nine floors. Anything else takes `make design-check` from green to failing four rows at once — which is precisely the failure GATES.md step 7b already recorded, and precisely the failure `CLAUDE.md`'s route-is-not-a-feature rule was written from.
