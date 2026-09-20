# STE false-positive survey: what the ratchet's exemptions rest on

**STATUS: EVIDENCE, RECORDED.** This is the survey `docs/decisions/D-a-ste-ratchet.md`
cites for every exemption class and for the printed floor. It classifies a stratified
sample of the vendored linter's own findings over this repo's real corpus, by hand,
against a rule stated before judging. Moved here from a session scratchpad on
2026-09-19 so the citations in `scripts/ste_measure.py`, `scripts/docs-audit.py` and the
decision entry point at a file this repository keeps, not one that expires with a
session. Section numbers are unchanged from the original — every `§N.M` citation in the
code still resolves to the same heading below. This document quotes STE violations as its own evidence. The ratchet reads it like any
other tracked markdown file, and its own count rises because of that — expected, and
named in the decision entry and the pull request, never hidden.

Scope: `docs/decisions/`, `docs/specs/` (incl. `docs/specs/store-scaling/`), `CLAUDE.md`, `README.md` — 266 files, 610,723 words by plain `wc -w`. Tool: `python3 $HOME/.claude/lint/ste_lint.py --no-color --format json --fail-on never <file>`, run once per file (266 subprocess calls). No repo `.ste.json`/`.ste.toml` was found, so all defaults apply (`max_words_procedural=20`, `max_words_descriptive=25`, mode=`auto`).

## 0. The measured gotcha, checked

The brief's premise — "passing several files in one call produces findings with no per-finding `file` key" — was tested directly (`multi1.md multi2.md` in one invocation) and **did not reproduce**: every finding in this installed version carries a correct `"path"` field, even in a multi-file batch. This is a deviation from the stated premise, not a finding about the corpus; it is reported as `unknown-premise, verified false` rather than silently accepted. Per-file invocation was used anyway, both as instructed and because per-finding source-line context (needed for classification) required reading each file regardless.

## 1. Exemptions, empirically (fixtures)

Fixtures live under `scratchpad/fixtures/`. Verdict is `exempt` (rule never fires inside the construct), `linted` (fires exactly as in plain prose), or `partly` (some rules exempted, others not).


| Construct | Verdict | Evidence |
|---|---|---|
| Fenced code block (\`\`\`/~~~) | **exempt** | `fence.md`: a semicolon, `etc.`, and `don't` inside the fence produced 0 findings. `segment_markdown` skips every line while `in_fence`. |
| YAML frontmatter (`---` at line 1) | **exempt** | `frontmatter.md`: a semicolon/`etc.`/`isn't` inside the frontmatter block produced 0 findings. Only recognized when the `---` is line 1. |
| Bare URL / autolink `<https://…>` / markdown link `[text](url)` | **exempt** | `url.md`: three long link constructs produced 0 findings; the only hit was a semicolon in the surrounding prose. `MASK_PATTERNS` replaces all three with an opaque one-word token before any rule runs (a link keeps only its visible label). |
| Inline backticks — semicolon/Latin/contraction *inside* the span | **exempt** | `backtick_semicolon.md`, `backtick_latin.md`, `backtick_contraction.md`: `` `a; b` ``, `` `e.g. foo` ``, `` `don't` `` each produced 0 findings — the `Masker` replaces backtick spans with an opaque token before `check_words` regexes run. |
| Inline backticks — contribution to STE001 sentence-length | **NOT exempt** | `backtick_run.md`: a sentence built from 24 comma-separated single-word backticked identifiers still triggered STE001 (29 words) — each backtick span counts as exactly one masked word, so a long run of short identifiers still inflates the sentence-length budget even though no single identifier's *content* is ever read. |
| Indented code block (4-space, no fence) | **linted** | `indented_code.md`: STE002/006/007/008 all fired on the indented line. `segment_markdown` has no indentation special-case; the leading whitespace becomes ordinary `prefix` and the body is treated as prose. |
| Markdown table row (`\| … \|`) | **partly** | `table.md`: STE006/007/008 (and other word-level rules) fire inside table cells exactly as in prose. But `check_text` explicitly skips `paragraph.kind in ("heading","table")` for all *sentence*-level rules — STE001, STE014 (paragraph-length), STE005 (noun-cluster), STE015, STE016 never fire on a table row. |
| Heading (`#`…`######`) | **partly** | `heading.md`: a heading of 20 words containing a semicolon/`Etc.`/`Don't` fired STE006/007/008 but **not** STE001, for the same `check_text` skip as tables. |
| List item (`-`/`*`/`1.`) | **linted** | `list.md`: STE001 (30-word item) and STE006/007/008 (second item) all fired. List paragraphs are not in the heading/table skip set; they get the full sentence-level and word-level treatment, plus an extra colon-based sub-split. |
| Blockquote (`>`) | **linted** | `blockquote.md`: STE001 and STE006/007/008 all fired. The `>` marker is stripped and the remainder folds into ordinary prose handling — no exemption at all. |

## 2. The sample

Seed: **20260919** (reported for re-draw; stratified `random.Random(20260919)`, per-stratum `shuffle` then slice). Population and sample sizes actually drawn (STE007 has ≤130 total in scope, so "every STE007" was taken whole; STE008's population is 147 (>40), so it got a 45-item stratified sample like STE001/STE006, not a full census):


| code | population (scope) | decisions | specs | root | sample drawn |
|---|---|---|---|---|---|
| STE001 | 7,162 | 4,592 | 2,542 | 28 | 45 (22/15/8) |
| STE006 | 2,638 | 1,350 | 1,270 | 18 | 45 (19/18/8) |
| STE007 | 130 | 24 | 102 | 4 | 130 (ALL) |
| STE008 | 147 | 93 | 52 | 2 | 45 (27/16/2) |

### Classification rule (stated before applying it)


- **GENUINE** — a person rewriting the prose would fix it, and the result would read at least as well, with no
  information lost. Ordinary multi-clause sentences, ordinary semicolon-joined independent clauses, and true
  Latin abbreviations (`e.g.`, `i.e.`, `etc.`, `et al.`, `ad hoc`) used as connective tissue in flowing prose fall
  here — the STE-suggested replacement ("for example", "that is", "and so on") is a strict, uncontroversial
  improvement.
- **ARTIFACT** — the finding sits on a construct the writer cannot change without deleting information or
  misquoting a source: (a) a markdown table cell/row; (b) a verbatim quotation (the product owner's own words,
  a code comment, or a cited external source) — rewriting would misquote the speaker; (c) an explicit enumeration
  (a citation list, a mutation-arm checklist, a file/directory listing) whose length is the list's, not the
  author's style; (d) a decision-citation shorthand, e.g. `(D31; …)`, where the semicolon separates an ID from
  its gloss; (e) a literal false match on a proper noun that merely contains the trigger substring (`VS Code`
  matched by the `vs` pattern); (f) an under-fenced code/shell example leaking real syntactic punctuation.
- **BORDERLINE** — defensible either way without the owner's call. This covers `via` and bare `vs`/`vs.` in
  ordinary (non-table, non-citation) prose: neither is a true *abbreviation* (nothing is shortened), both read
  as fully-assimilated modern English to many style guides, and whether swapping them for "through"/"using"/
  "compared with" is an *improvement* — rather than a lateral, rule-satisfying edit — is a judgment call, not a
  mechanical one.

### STE001 — sentence-length

n=45 — GENUINE 39 (86.7%), ARTIFACT 5 (11.1%), BORDERLINE 1 (2.2%)

| # | file:line:col | matched text / word count | verdict | why |
|---|---|---|---|---|
| 0 | `docs/decisions/D176-the-primary-checkout-syncs-itself.md:182:81` | So what a reader wants from it is not *do it anyway* but *stop doing it* — which is why it is on the refusals too: a ref | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 1 | `docs/decisions/D048-a-send-is-a-cart-of-boxes-a-run-is-still-one-box.md:15:91` | D29's validate-everything-then-write-everything with an invoice instead of a queue answer: a bad flag on the fourth box  | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 2 | `docs/decisions/D035-a-number-that-cannot-be-read-falls-back-to-the-name-and.md:13:332` | A rung that trusts the name when the number finds nothing is not a weaker check; it is the check aimed at the field that | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 3 | `docs/decisions/D016-the-docs-are-checked-mechanically-the-prose-is-checked-by.md:64:60` | Both legs of the threshold check above were *substring* tests against the whole section, so lowering T1's CODE to CODE — | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 4 | `docs/decisions/D119-the-copy-the-walk-stands-on-is-a-row-like-every-other-and.md:72:116` | Shrinking the photo column is what D32 and D38 spend the pixel budget against — D38 *raised* it on the owner's own ask — | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 5 | `docs/decisions/D109-a-price-is-a-fact-about-a-listing-and-the-store-remembers.md:56:86` | This is the real term D100's proxy was standing in for, and it is available for a SKU no card here carries as readily as | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 6 | `docs/decisions/D003-variant-resolution-ladder.md:5:324` | It reads CODE and CODE off the live inventory record, so a card the owner has ruled on in the review queue keeps that ru | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 7 | `docs/decisions/D118-a-press-changes-what-is-on-the-screen-never-where-the.md:17:32` | A departed copy drew none (D68), so the lens vanished on the press that sold the card and came back the moment the walk  | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 8 | `docs/decisions/D198-home-review-tile-counts-both-queues.md:37:31` | CODE's top banner has the identical shape of gap — a parked-only state falls through toward "Clear — nothing is owed any | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 9 | `docs/decisions/D031-one-owner-side-view-of-stored-cards-and-the-fulfiller.md:37:70` | Recorded because it was argued the wrong way round and the owner corrected it: *"do not concern yourself with fulfiller  | **ARTIFACT** | sentence body is the verbatim owner quote *"do not concern yourself with fulfiller concerns..."*; length is the quote's, not the author's prose |
| 10 | `docs/decisions/D009-threshold-and-floor-are-both-0-40.md:24:1` | The join preserves the sub-threshold price distribution in bands rather than lumping it, because *everything under $0.40 | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 11 | `docs/decisions/D049-the-pricing-answer-is-one-file-and-a-card-can-be-held.md:54:84` | Every other handler in the app returns on CODE; on this one the hands are in a price field essentially always, so that r | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 12 | `docs/decisions/D167-the-queue-is-refreshed-where-it-stands.md:41:1` | **A card that has LEFT THE BOX is skipped, not re-asked about** (D26, D83) — CODE already draws that line for a run and  | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 13 | `docs/decisions/D079-the-reading-goes-on-every-row-because-the-operator.md:79:1` | The owner's second instruction: *"I don't need the prices for the rows that have none left."* CODE is the field CODE alr | **ARTIFACT** | sentence body is the verbatim owner quote *"I don't need the prices for the rows that have none left."* |
| 14 | `docs/decisions/D114-the-status-requirement-is-answered-by-a-remembered-tick.md:115:53` | CODE returns UNASKED on a throw, and UNASKED is the safe direction: the unsafe one imports orders delivered a month ago  | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 15 | `docs/decisions/D190-unclaim-completes-the-remedy.md:51:77` | A different entry sharing the number by coincidence is not that danger; it is the collision the command exists to fix, a | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 16 | `docs/decisions/D180-a-selection-of-cards.md:25:127` | **12 at CODE 1200, 2 at 900, 1 at 1568** — and the three that differ are three separate presses on three different days, | **BORDERLINE** | front half is an irreducible 3-point data enumeration (12 at 1200, 2 at 900, 1 at 1568); back half is ordinary prose - a rewrite could split after the data but the data itself cannot shrink |
| 17 | `docs/decisions/D149-a-section-number-that-resolves-is-not-a-citation-that-is.md:9:1` | **Nine other sites cite section 11 and are RIGHT** — not merely untouched: every one is about the capture server's concu | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 18 | `docs/decisions/D046-a-card-the-pipeline-could-not-place-is-offered-the.md:21:418` | The search box is a form, so Enter submits it, and CODE is what stops a typed CODE from answering the card — asserted as | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 19 | `docs/decisions/D018-a-generator-may-write-nothing-that-writes-may-gate-a.md:19:54` | An id in CODE that the file does not cite is invisible to the row and to the generator alike, and removing one stays a p | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 20 | `docs/decisions/D163-hash-before-decode.md:50:18` | **A reorder that left those alone would have reported all 464 healthy cached cards as unreadable**, counted them as neit | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 21 | `docs/decisions/D180-a-selection-of-cards.md:139:304` | **The mitigation is the preflight's honesty rather than a ceiling** — it names the figure and the count in cards before  | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 22 | `docs/specs/order-flow.md:245:11` | A silently sorted layout would relabel a box without saying so, which is precisely the failure D10's amendment accepts t | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 23 | `docs/specs/logo.md:848:1` | **The reopening condition is a theme-dependent opacity**, which was considered and rejected here: dark could take a lowe | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 24 | `docs/specs/store-scaling/06-orders.md:554:71` | If item 1 (the CODE guard) has already landed by the time this item is implemented, run CODE after this item's changes a | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 25 | `docs/specs/batch-script.md:208:61` | The second exists because the first found nothing in any of the 53 Gate B photographs — see CODE's T6 section for the me | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 26 | `docs/specs/undo.md:35:47` | CODE is the only undo refusal in CODE and it is a STATE test, not a clock: it refuses once a card is identified or its S | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 27 | `docs/specs/capture-server.md:397:61` | D10's amendment made that a special case rather than the rule, and D10's amendment of 2026-08-29 deleted the special cas | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 28 | `docs/specs/stale-listings.md:179:49` | **It was the constant on both, read by nobody, until the owner set the cut-off to CODE**: CODE over a 354-row worklist w | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 29 | `docs/specs/store-scaling/08-search-fts5.md:146:65` | Reuse the Python functions by adding two derived, indexed columns to the CODE table, populated at write time the same wa | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 30 | `docs/specs/order-pipeline.md:355:1` | The screen is CODE: the way in (paste and fetch behind one control), the six-way counts breakdown drawn including its ze | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 31 | `docs/specs/order-pipeline.md:640:39` | So landing the walk on the LINE puts its whole pick list on screen for free, and the queue advances per line: three of X | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 32 | `docs/specs/mechanization-backlog.md:1099:37` | (b) docs/specs/: nine specs (order-pipeline, stale-listings, code-cards, motion-trigger, capture-app, batch-script, one- | **ARTIFACT** | length is dominated by an explicit enumeration of 9 spec filenames in parentheses |
| 33 | `docs/specs/audit-retirement.md:248:86` | A generator that rewrites a doc from a code constant is not the audit, breaks none of D16's letter, and recreates its fa | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 34 | `docs/specs/order-flow.md:558:1` | The objection was that the sale write belongs to the Fulfillment view, which earns it by carrying the guards CODE assert | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 35 | `docs/specs/order-flow.md:19:34` | A session that reads a ratified decision as a built feature will go looking for code that is not there; a session that r | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 36 | `docs/specs/batch-script.md:324:34` | It is written that way because the alternative was measured and failed: three parallel CODE functions each re-implemente | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 37 | `CLAUDE.md:16:29` | That includes the checkout (CODE), the CLI CODE, the Python packages (CODE), the store on disk (CODE), CODE, every wire  | **ARTIFACT** | length is dominated by an enumeration of the checkout/CLI/package paths CLAUDE.md must name exhaustively |
| 38 | `README.md:208:82` | The build goes into a sibling directory and is renamed in, because CODE empties its output directory before it writes —  | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 39 | `README.md:176:88` | The published screen count in this file, in CLAUDE.md and in CODE was wrong seven times with nothing reading it — five p | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 40 | `README.md:222:60` | CODE runs the capture server in the foreground, watching nothing, and is refused beside CODE — that collision fails loud | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 41 | `README.md:188:1` | All thirteen open at a hash, and the Fulfiller's view opens **without the shell** the other twelve carry — its row in CO | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 42 | `README.md:225:28` | CODE renders CODE into CODE, and CODE asserts CODE's Fulfillment floors in a real browser — behind a machine-wide lock,  | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |
| 43 | `README.md:202:7` | It prints the link, **restarts itself whenever you edit Python** under CODE, CODE, CODE, CODE, CODE or CODE, and **rebui | **ARTIFACT** | length is dominated by an enumeration of 6 directory names (`server/`, `store/`, ... `geometry/`) |
| 44 | `README.md:183:1` | **CODE and CODE are two stages of one hub** — CODE exports it, CODE points the second route at it — and CODE is the one  | **GENUINE** | ordinary multi-clause prose; a split/trim would read better without losing information |

### STE006 — semicolon

n=45 — GENUINE 37 (82.2%), ARTIFACT 7 (15.6%), BORDERLINE 1 (2.2%)

| # | file:line:col | matched text / word count | verdict | why |
|---|---|---|---|---|
| 0 | `docs/decisions/D134-a-departed-record-is-buried-not-kept-the-box-goes-and-the.md:63:78` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 1 | `docs/decisions/D133-a-branch-is-judged-by-what-it-lands-and-a-file-put-back.md:77:10` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 2 | `docs/decisions/D045-the-copies-list-is-a-way-back-into-the-walk-and-the.md:23:340` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 3 | `docs/decisions/D065-the-export-is-asked-for-and-the-boxs-own-claims-are-the.md:122:1095` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 4 | `docs/decisions/D049-the-pricing-answer-is-one-file-and-a-card-can-be-held.md:54:144` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 5 | `docs/decisions/D033-the-pipeline-is-reachable-from-a-screen-and-one-route-can.md:13:45` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 6 | `docs/decisions/D187-a-slug-two-branches-both-still-hold-unclaimed.md:40:69` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 7 | `docs/decisions/D207-one-poller.md:5:269` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 8 | `docs/decisions/D165-run-binds-to-bid.md:85:163` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 9 | `docs/decisions/D094-banchi-is-the-products-name-and-bn-is-the-vocabulary.md:9:183` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 10 | `docs/decisions/D079-the-reading-goes-on-every-row-because-the-operator.md:52:67` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 11 | `docs/decisions/D033-the-pipeline-is-reachable-from-a-screen-and-one-route-can.md:13:205` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 12 | `docs/decisions/D144-a-card-that-will-not-settle-is-photographed-off-the.md:109:4` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 13 | `docs/decisions/D136-the-suite-is-sharded-and-never-widened-a-sleep-is-a-wait.md:21:574` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 14 | `docs/decisions/D101-a-claim-a-screen-names-is-a-claim-a-screen-can-fix-and.md:23:135` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 15 | `docs/decisions/D071-a-card-with-no-slot-is-ranked-like-every-other-and-it-is.md:16:468` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 16 | `docs/decisions/D065-the-export-is-asked-for-and-the-boxs-own-claims-are-the.md:59:104` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 17 | `docs/decisions/D164-the-undo-stack-is-the-sitting-not-the-drawer.md:141:66` | None | **ARTIFACT** | semicolons delimit a 7-item enumeration of mutation-testing arms ("the box filter back on the stack; ... the drawer label dropped; ...") |
| 18 | `docs/decisions/D028-the-review-answer-gets-an-undo-window-and-the-list-stops.md:14:306` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 19 | `docs/specs/mechanization-backlog.md:780:90` | None | **ARTIFACT** | semicolons delimit a checklist of "six named families" test items, each with its own file:line citation |
| 20 | `docs/specs/emit-reconcile-placement.md:3:131` | None | **ARTIFACT** | a changelog/status line; each semicolon-joined clause carries its own decision citation, e.g. "(D86 amended)", "(D9 amended)" |
| 21 | `docs/specs/stable-card-id.md:760:308` | None | **ARTIFACT** | semicolons delimit an 8-item enumeration of mutation arms ("delete X; delete Y; ... make Z; make W") |
| 22 | `docs/specs/store-scaling/07-value-and-aggregates.md:107:79` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 23 | `docs/specs/capture-app.md:452:71` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 24 | `docs/specs/stale-listings.md:562:11` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 25 | `docs/specs/store-scaling/07-value-and-aggregates.md:918:82` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 26 | `docs/specs/capture-server.md:77:77` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 27 | `docs/specs/mechanization-backlog.md:125:38` | None | **ARTIFACT** | semicolons are shell-syntax inside an under-fenced command example (`>/dev/null; do sleep 5; done`), not prose punctuation |
| 28 | `docs/specs/multi-game.md:435:37` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 29 | `docs/specs/mechanization-backlog.md:271:9` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 30 | `docs/specs/store-scaling.md:98:42` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 31 | `docs/specs/order-pipeline.md:260:24` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 32 | `docs/specs/ui-research.md:172:158` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 33 | `docs/specs/mechanization-backlog.md:821:55` | None | **ARTIFACT** | semicolon opens a "Must keep passing" checklist enumerating call sites, matching the pattern in #19/#21 |
| 34 | `docs/specs/store-scaling/04-copies-out.md:384:48` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 35 | `docs/specs/stable-card-id.md:772:1112` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 36 | `docs/specs/store-scaling/07-value-and-aggregates.md:456:92` | None | **BORDERLINE** | semicolon sits inside a compact parenthetical formula/annotation (`Math.round(...)`; `under_cutoff`/`at_or_over` read directly) rather than plain narrative prose; splitting is possible but changes a deliberate terse-spec convention |
| 37 | `README.md:229:36` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 38 | `README.md:205:83` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 39 | `CLAUDE.md:365:88` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 40 | `README.md:186:5` | None | **ARTIFACT** | semicolon is a decision-citation separator, "(D31; #/boxes and #/pull are gone...)", not a clause joiner |
| 41 | `CLAUDE.md:501:20` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 42 | `README.md:142:24` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 43 | `CLAUDE.md:920:12` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |
| 44 | `CLAUDE.md:412:29` | None | **GENUINE** | semicolon joins two independent clauses of ordinary prose; two sentences read at least as well |

### STE007 — Latin abbreviation (ALL findings in scope)

n=130 — GENUINE 37 (28.5%), ARTIFACT 23 (17.7%), BORDERLINE 70 (53.8%)

| # | file:line:col | matched text / word count | verdict | why |
|---|---|---|---|---|
| 0 | `docs/decisions/D185-a-row-that-examined-nothing-says-so.md:47:367` | i.e. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 1 | `docs/decisions/D187-a-slug-two-branches-both-still-hold-unclaimed.md:6:32` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 2 | `docs/decisions/D187-a-slug-two-branches-both-still-hold-unclaimed.md:22:24` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 3 | `docs/decisions/D163-hash-before-decode.md:80:46` | i.e. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 4 | `docs/decisions/D163-hash-before-decode.md:108:74` | i.e. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 5 | `docs/decisions/D032-the-pixel-budget-is-spent-on-the-card-not-the-desk.md:19:46` | vs | **ARTIFACT** | table row/cell (`| ... | vs today |`) |
| 6 | `docs/decisions/D204-the-drawer-scrolls-above-its-foot.md:50:75` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 7 | `docs/decisions/D054-a-re-emit-adds-it-never-subtracts.md:25:38` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 8 | `docs/decisions/D173-a-rule-with-no-reader-is-advice.md:8:84` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 9 | `docs/decisions/D194-copy-ratchet.md:59:39` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 10 | `docs/decisions/D045-the-copies-list-is-a-way-back-into-the-walk-and-the.md:23:269` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 11 | `docs/decisions/D176-the-primary-checkout-syncs-itself.md:59:17` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 12 | `docs/decisions/D188-a-join-with-no-run-directory.md:29:389` | vs | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 13 | `docs/decisions/D188-a-join-with-no-run-directory.md:47:577` | vs | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 14 | `docs/decisions/D188-a-join-with-no-run-directory.md:47:616` | vs | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 15 | `docs/decisions/D002-identification-is-claude-haiku-vision-owned-end-to-end.md:3:222` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 16 | `docs/decisions/D077-the-pipelines-rows-can-be-the-wrong-card-so-the-export-is.md:18:80` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 17 | `docs/decisions/D154-the-cameras-automatic-functions-are-inputs-to-the.md:55:10` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 18 | `docs/decisions/_someday-worth-doing-blocking-nothing.md:86:55` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 19 | `docs/decisions/D145-a-box-has-an-index-nobody-sees-because-the-number-on-the.md:7:197` | etc. | **ARTIFACT** | verbatim owner-transcript quote ("...run a long time ago etc. it's confusing.") |
| 20 | `docs/decisions/D050-an-interactive-elements-feedback-is-the-products-not-each.md:17:32` | vs | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 21 | `docs/decisions/D050-an-interactive-elements-feedback-is-the-products-not-each.md:18:32` | vs | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 22 | `docs/decisions/D050-an-interactive-elements-feedback-is-the-products-not-each.md:19:32` | vs | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 23 | `docs/decisions/D209-orders-sort-filter.md:26:74` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 24 | `docs/specs/shipping-export.md:125:23` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 25 | `docs/specs/ui-research.md:69:257` | etc. | **ARTIFACT** | verbatim quotation of Superhuman's own copy, cited with a link |
| 26 | `docs/specs/ui-research.md:86:49` | VS | **ARTIFACT** | false match on the proper noun "VS Code", not the abbreviation "vs." |
| 27 | `docs/specs/ui-research.md:102:119` | vs | **ARTIFACT** | numeric result comparison quoted from a cited study (0 errors vs 2) |
| 28 | `docs/specs/ui-research.md:104:112` | vs | **ARTIFACT** | numeric result comparison quoted from a cited study (0.949 vs 0.738) |
| 29 | `docs/specs/ui-research.md:156:223` | vs | **ARTIFACT** | numeric result comparison quoted from a cited study (1.57s vs 2.11s vs 2.40s) |
| 30 | `docs/specs/ui-research.md:156:241` | vs | **ARTIFACT** | numeric result comparison quoted from a cited study (duplicate offset, same sentence as #29) |
| 31 | `docs/specs/ui-research.md:182:143` | ad hoc | **ARTIFACT** | verbatim quotation of a GitLab issue-tracker comment, cited with a link |
| 32 | `docs/specs/ui-research.md:186:286` | vs | **ARTIFACT** | numeric result comparison quoted from a cited study (1,178 min vs 890) |
| 33 | `docs/specs/ui-research.md:195:131` | VS | **ARTIFACT** | false match on the proper noun "VS Code" |
| 34 | `docs/specs/ui-research.md:213:10` | et al. | **ARTIFACT** | academic citation convention "<Author> et al." naming a paper's authors |
| 35 | `docs/specs/ui-research.md:230:572` | VS | **ARTIFACT** | false match on the proper noun "VS Code" |
| 36 | `docs/specs/ui-research.md:247:108` | vs | **ARTIFACT** | table row/cell |
| 37 | `docs/specs/ui-research.md:254:170` | VS | **ARTIFACT** | false match on the proper noun "VS Code" (also a table row) |
| 38 | `docs/specs/mechanization-backlog.md:879:32` | i.e. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 39 | `docs/specs/logo.md:1291:14` | vs | **ARTIFACT** | table row/cell |
| 40 | `docs/specs/batch-script.md:141:55` | vs | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 41 | `docs/specs/batch-script.md:190:58` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 42 | `docs/specs/audit-retirement.md:525:86` | vs | **ARTIFACT** | table row/cell |
| 43 | `docs/specs/multi-game.md:100:68` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 44 | `docs/specs/store-scaling.md:57:274` | via | **ARTIFACT** | table row/cell |
| 45 | `docs/specs/store-scaling.md:59:48` | via | **ARTIFACT** | table row/cell |
| 46 | `docs/specs/stale-listings.md:590:38` | via | **ARTIFACT** | table row/cell |
| 47 | `docs/specs/tcgplayer-portal-api.md:28:79` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 48 | `docs/specs/store-scaling/02-per-box-read.md:23:81` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 49 | `docs/specs/store-scaling/02-per-box-read.md:85:52` | vs | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 50 | `docs/specs/store-scaling/02-per-box-read.md:129:81` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 51 | `docs/specs/store-scaling/02-per-box-read.md:206:38` | etc. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 52 | `docs/specs/store-scaling/02-per-box-read.md:396:78` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 53 | `docs/specs/store-scaling/02-per-box-read.md:663:51` | i.e. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 54 | `docs/specs/store-scaling/02-per-box-read.md:665:31` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 55 | `docs/specs/store-scaling/02-per-box-read.md:668:51` | i.e., | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 56 | `docs/specs/store-scaling/02-per-box-read.md:1273:35` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 57 | `docs/specs/store-scaling/02-per-box-read.md:1417:56` | vs | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 58 | `docs/specs/store-scaling/02-per-box-read.md:1451:42` | e.g., | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 59 | `docs/specs/store-scaling/01-guard.md:148:58` | etc. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 60 | `docs/specs/store-scaling/01-guard.md:383:81` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 61 | `docs/specs/store-scaling/01-guard.md:709:38` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 62 | `docs/specs/store-scaling/07-value-and-aggregates.md:30:44` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 63 | `docs/specs/store-scaling/07-value-and-aggregates.md:133:68` | vs. | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 64 | `docs/specs/store-scaling/07-value-and-aggregates.md:461:4` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 65 | `docs/specs/store-scaling/07-value-and-aggregates.md:489:66` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 66 | `docs/specs/store-scaling/07-value-and-aggregates.md:549:86` | i.e. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 67 | `docs/specs/store-scaling/07-value-and-aggregates.md:557:20` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 68 | `docs/specs/store-scaling/07-value-and-aggregates.md:564:72` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 69 | `docs/specs/store-scaling/07-value-and-aggregates.md:587:60` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 70 | `docs/specs/store-scaling/07-value-and-aggregates.md:599:12` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 71 | `docs/specs/store-scaling/07-value-and-aggregates.md:648:16` | etc. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 72 | `docs/specs/store-scaling/07-value-and-aggregates.md:990:15` | vs. | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 73 | `docs/specs/store-scaling/05-readings-writer.md:358:53` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 74 | `docs/specs/store-scaling/05-readings-writer.md:533:133` | via | **ARTIFACT** | table row/cell |
| 75 | `docs/specs/store-scaling/05-readings-writer.md:605:10` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 76 | `docs/specs/store-scaling/03-history.md:32:13` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 77 | `docs/specs/store-scaling/03-history.md:38:74` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 78 | `docs/specs/store-scaling/03-history.md:178:66` | vs. | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 79 | `docs/specs/store-scaling/03-history.md:223:44` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 80 | `docs/specs/store-scaling/03-history.md:500:50` | via | **ARTIFACT** | table row/cell |
| 81 | `docs/specs/store-scaling/03-history.md:501:54` | via | **ARTIFACT** | table row/cell |
| 82 | `docs/specs/store-scaling/03-history.md:517:57` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 83 | `docs/specs/store-scaling/03-history.md:677:32` | e.g., | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 84 | `docs/specs/store-scaling/03-history.md:677:54` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 85 | `docs/specs/store-scaling/03-history.md:688:31` | etc. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 86 | `docs/specs/store-scaling/03-history.md:690:86` | i.e., | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 87 | `docs/specs/store-scaling/03-history.md:704:90` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 88 | `docs/specs/store-scaling/03-history.md:711:31` | e.g., | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 89 | `docs/specs/store-scaling/03-history.md:853:56` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 90 | `docs/specs/store-scaling/03-history.md:867:43` | vs. | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 91 | `docs/specs/store-scaling/04-copies-out.md:96:12` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 92 | `docs/specs/store-scaling/04-copies-out.md:131:57` | i.e. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 93 | `docs/specs/store-scaling/04-copies-out.md:157:65` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 94 | `docs/specs/store-scaling/04-copies-out.md:192:19` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 95 | `docs/specs/store-scaling/04-copies-out.md:361:88` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 96 | `docs/specs/store-scaling/04-copies-out.md:503:28` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 97 | `docs/specs/store-scaling/04-copies-out.md:504:50` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 98 | `docs/specs/store-scaling/04-copies-out.md:529:72` | i.e., | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 99 | `docs/specs/store-scaling/04-copies-out.md:537:43` | vs. | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 100 | `docs/specs/store-scaling/04-copies-out.md:601:32` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 101 | `docs/specs/store-scaling/04-copies-out.md:770:41` | vs. | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 102 | `docs/specs/store-scaling/04-copies-out.md:785:63` | etc. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 103 | `docs/specs/store-scaling/06-orders.md:24:17` | vs | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 104 | `docs/specs/store-scaling/06-orders.md:24:39` | vs | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 105 | `docs/specs/store-scaling/06-orders.md:46:43` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 106 | `docs/specs/store-scaling/06-orders.md:120:36` | i.e. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 107 | `docs/specs/store-scaling/06-orders.md:155:29` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 108 | `docs/specs/store-scaling/06-orders.md:160:42` | etc. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 109 | `docs/specs/store-scaling/06-orders.md:510:30` | vs. | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 110 | `docs/specs/store-scaling/06-orders.md:510:70` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 111 | `docs/specs/store-scaling/06-orders.md:529:83` | i.e., | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 112 | `docs/specs/store-scaling/06-orders.md:534:34` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 113 | `docs/specs/store-scaling/06-orders.md:582:69` | etc. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 114 | `docs/specs/store-scaling/06-orders.md:644:76` | e.g. | **GENUINE** | true Latin abbreviation in ordinary prose; swap for the plain-English gloss loses nothing |
| 115 | `docs/specs/store-scaling/06-orders.md:661:88` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 116 | `docs/specs/store-scaling/08-search-fts5.md:38:22` | vs. | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 117 | `docs/specs/store-scaling/08-search-fts5.md:54:19` | vs. | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 118 | `docs/specs/store-scaling/08-search-fts5.md:592:57` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 119 | `docs/specs/store-scaling/08-search-fts5.md:633:66` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 120 | `docs/specs/store-scaling/08-search-fts5.md:673:45` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 121 | `docs/specs/store-scaling/08-search-fts5.md:679:71` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 122 | `docs/specs/store-scaling/08-search-fts5.md:685:54` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 123 | `docs/specs/store-scaling/08-search-fts5.md:747:22` | vs. | **BORDERLINE** | 'vs' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 124 | `docs/specs/store-scaling/08-search-fts5.md:822:15` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 125 | `docs/specs/store-scaling/08-search-fts5.md:847:33` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 126 | `CLAUDE.md:370:73` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 127 | `CLAUDE.md:409:67` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 128 | `CLAUDE.md:472:71` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |
| 129 | `CLAUDE.md:597:18` | via | **BORDERLINE** | 'via' is a fully-assimilated English word/comparator in ordinary prose here, not an abbreviation; whether replacing it is an improvement is a style call |

### STE008 — contraction

n=45 — GENUINE 2 (4.4%), ARTIFACT 42 (93.3%), BORDERLINE 1 (2.2%)

| # | file:line:col | matched text / word count | verdict | why |
|---|---|---|---|---|
| 0 | `docs/decisions/D181-the-order-is-taken-once-and-a-sale-may-not-retake-it.md:11:76` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 1 | `docs/decisions/D181-the-order-is-taken-once-and-a-sale-may-not-retake-it.md:11:38` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 2 | `docs/decisions/D050-an-interactive-elements-feedback-is-the-products-not-each.md:35:141` | isn't | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 3 | `docs/decisions/D036-the-run-says-what-the-model-read-the-store-says-which.md:13:68` | don't | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 4 | `docs/decisions/D086-the-pricing-answer-is-one-file-for-the-store-and-the.md:32:428` | aren't | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 5 | `docs/decisions/D031-one-owner-side-view-of-stored-cards-and-the-fulfiller.md:9:46` | wouldn't | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 6 | `docs/decisions/D170-a-pokemon-run-names-its-sets-or-the-fetch-refuses.md:47:256` | didn't | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 7 | `docs/decisions/D147-the-claim-is-spent-on-the-oldest-copies-because-a-card.md:3:278` | that's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 8 | `docs/decisions/D214-gross-sales-retrospective.md:75:60` | we're | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 9 | `docs/decisions/D156-every-copy-tcgplayer-does-not-hold-is-one-worklist-and-a.md:5:136` | there's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 10 | `docs/decisions/D068-a-departed-cards-label-names-the-record-because-two-of.md:33:142` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 11 | `docs/decisions/D118-a-press-changes-what-is-on-the-screen-never-where-the.md:3:355` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 12 | `docs/decisions/D007-duplicates-aggregate-by-sku-at-join-time.md:62:401` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 13 | `docs/decisions/D090-the-envelope-is-the-unit-of-the-write-and-an-order-drives.md:5:126` | you're | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 14 | `docs/decisions/D113-a-line-closes-three-ways-and-only-one-of-them-claims-a.md:4:49` | can't | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 15 | `docs/decisions/D103-staleness-is-a-filter-and-not-a-gate-the-record-holds.md:3:576` | that's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 16 | `docs/decisions/D090-the-envelope-is-the-unit-of-the-write-and-an-order-drives.md:9:191` | can't | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 17 | `docs/decisions/D031-one-owner-side-view-of-stored-cards-and-the-fulfiller.md:9:76` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 18 | `docs/decisions/D144-a-card-that-will-not-settle-is-photographed-off-the.md:5:70` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 19 | `docs/decisions/D176-the-primary-checkout-syncs-itself.md:8:63` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 20 | `docs/decisions/D090-the-envelope-is-the-unit-of-the-write-and-an-order-drives.md:39:250` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 21 | `docs/decisions/D133-a-branch-is-judged-by-what-it-lands-and-a-file-put-back.md:156:72` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 22 | `docs/decisions/D162-name-beats-a-disputed-number.md:147:10` | shouldn't | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 23 | `docs/decisions/D153-the-restore-asks-which-drawer-not-which-number-and-the.md:53:64` | shouldn't | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 24 | `docs/decisions/D087-the-reconcile-is-store-wide-and-what-it-writes-is-live.md:3:233` | you've | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 25 | `docs/decisions/D107-the-rule-only-ever-marks-down-the-operator-may-point.md:3:238` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 26 | `docs/decisions/D105-the-markdown-lives-where-prices-are-decided-and-one-file.md:3:149` | that's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 27 | `docs/specs/order-walk-plan.md:435:57` | can't | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 28 | `docs/specs/ui-research.md:5:24` | you're | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 29 | `docs/specs/store-scaling/01-guard.md:20:32` | don't | **GENUINE** | ordinary author prose using a contraction for register/punch; de-contracting reads at least as well |
| 30 | `docs/specs/store-scaling.md:57:854` | aren't | **ARTIFACT** | contraction sits inside a markdown table cell (a `|`-delimited row), not a sentence |
| 31 | `docs/specs/undo.md:141:15` | that's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 32 | `docs/specs/stale-listings.md:395:81` | that's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 33 | `docs/specs/store-scaling.md:205:9` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 34 | `docs/specs/store-scaling/00-phases.md:113:53` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 35 | `docs/specs/ui-research.md:65:867` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 36 | `docs/specs/order-walk-plan.md:415:56` | can't | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 37 | `docs/specs/order-pipeline.md:775:19` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 38 | `docs/specs/store-scaling/02-per-box-read.md:1359:43` | you're | **BORDERLINE** | "while you're in there" is a quoted idiom in the author's own voice (not an owner transcript); defensible either way |
| 39 | `docs/specs/code-cards.md:270:18` | don't | **ARTIFACT** | "replace-don't-refund" is a coined hyphenated policy label; de-contracting breaks the compound term |
| 40 | `docs/specs/undo.md:140:66` | there's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 41 | `docs/specs/ui-research.md:194:39` | don't | **GENUINE** | ordinary author prose using a contraction for register/punch; de-contracting reads at least as well |
| 42 | `docs/specs/order-walk-plan.md:33:36` | it's | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 43 | `README.md:271:68` | don't | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |
| 44 | `README.md:272:29` | we've | **ARTIFACT** | verbatim quotation (owner transcript or cited source); de-contracting would misquote the speaker |

### Borderline cases, listed individually for the owner

STE001 and STE006 borderline cases (1 each) are inline in their tables above (index 16 and 36 respectively). STE008's single borderline case is index 38 in its table above. STE007's 70 borderline cases are every row marked **BORDERLINE** in the STE007 table above (all `via`/`vs`/`vs.` hits in ordinary prose, not in a table, not a `VS Code` false match, and not attached to a citation-quoted statistic) — each carries its own `file:line:col` in that table, so any one of them can be pulled up and re-judged individually.

## 3. The floor

Total words in scope (plain `wc -w`): **610,723**. Total findings for the four in-scope codes: **10,077** (STE001 7,162, STE006 2,638, STE007 130, STE008 147) — an unfiltered combined density of **16.50 errors / 1,000 words**.

Extrapolating each code's sample artifact-fraction onto its full population (STE007's fraction is exact — the sample is the whole population, not an extrapolation):


| code | artifact % (sample) | +borderline % | artifact floor (count) | +borderline floor (count) | artifact floor (density/1k words) | +borderline floor (density/1k words) |
|---|---|---|---|---|---|---|
| STE001 | 11.1% | 13.3% | ~796 | ~955 | 1.303 | 1.564 |
| STE006 | 15.6% | 17.8% | ~410 | ~469 | 0.672 | 0.768 |
| STE007 | 17.7% (exact) | 71.5% (exact) | 23 | 93 | 0.038 | 0.152 |
| STE008 | 93.3% | 95.6% | ~137 | ~141 | 0.225 | 0.230 |
| **combined** | — | — | **~1,366** | **~1,657** | **2.237** | **2.714** |

Reading this straight: **no density threshold set below ~2.24 errors/1,000 words (combined, across STE001/006/007/008) can ever be satisfied on this corpus as it stands**, because that many findings are not prose defects — they are table cells, verbatim quotes, citations, enumerations, decision-citation shorthand, and one outright false match. A ratchet drawn tighter than that floor is unsatisfiable by construction, not by insufficient editing. If the borderline `via`/`vs` calls are resolved against the writer (i.e. counted as also-unfixable), the floor rises to ~2.71/1,000 words (~1,657 total errors). Per-code, the STE008 (contraction) floor is the starkest: at least 93% of the sampled STE008 findings are inside verbatim quotations of the product owner's own words — a contraction threshold for this rule is close to unsatisfiable on this corpus at any setting near today's observed rate.

These floors use a plain `wc -w` word count as the denominator; the authoritative corpus size and density definition belong to the lane counting the corpus, and this floor should be recomputed against that ruler once published — the *fraction* (artifact share per code) does not depend on which word-count denominator is used, only the density figure does.

## 4. Exemption classes worth building


1. **Markdown table row.** Recognized identically to how `ste_lint.py` itself already recognizes it for STE001/014/005/015/016
   (`TABLE_ROW = re.compile(r"^\s*\|")`), but the exemption is not extended to STE006/007/008 (or the other word-level
   rules). Mechanical fix: apply the same `paragraph.kind == "table"` skip to `check_words`, or have a wrapper drop
   any finding whose source line, stripped, starts with `|`. Accounts for **11 of 130** STE007 sample findings (all
   of STE007's population, since the sample is a census) and **1 of 45** STE008 findings; STE006 had a few sample
   hits that were citation-shorthand rather than table rows, so this class is narrower there.
2. **Verbatim quotation of a person's own words.** Every STE008 (contraction) finding whose line is inside a
   markdown blockquote (`^\s*>`) or wrapped in `*"…"*` (this repo's own convention for the product owner's quoted
   speech) is a false positive by construction — you cannot "fix" what someone said. Mechanical recognition: a line
   (or the run of lines between an opening `*"` /  `>` and its matching close) inside a blockquote block or an
   `*"…"*`-delimited span. Accounts for **≥40 of 45** STE008 sample findings (89%+) and several STE001/STE007 hits too
   (e.g. STE001 sample #9, #13; STE007 sample #19, #25, #31 are inside quoted transcripts or cited third-party text).
3. **Decision-citation shorthand `(D<n>; …)` / `(D<n> amended)`.** A parenthetical whose first token matches
   `\(D\d+[,;]` is a citation, not a clause; recognized mechanically by that regex anchored at `(`. Accounts for
   2 of the 45 STE006 sample findings directly (#20, #40) and is a small but clean, fully-mechanical class.
4. **Enumeration collapsed into one paragraph** (a "Six named families:" / "Seven mutation arms:" checklist joined
   by semicolons, or a parenthetical list of file/spec names). Harder to detect by regex alone, but a workable
   proxy: a sentence/paragraph containing **3 or more** semicolons, or **3 or more** backtick/parenthesized items
   separated only by commas after a colon, is very likely an enumeration rather than argued prose. Accounts for
   4 of 45 STE006 sample findings (#17, #19, #21, #33) and 2 of 45 STE001 sample findings (#32, #43); flag rather
   than auto-exempt, since some genuinely long enumerations should still be turned into real bullet lists.
5. **False match on a two-word proper noun containing the trigger substring** (`VS Code`, and by the same logic
   any future `Node.js`-style collision). Mechanical recognition for this specific one: `\bVS\s+Code\b` immediately
   surrounding a `vs` match should suppress STE007. Accounts for 4 of 130 STE007 sample/population findings — small,
   but a pure bug rather than a judgment call, and worth an allowlist entry regardless of what else is exempted.

## Fixtures and scripts

- Fixtures: `scratchpad/fixtures/*.md`

- Raw per-file findings for the scoped corpus: `scratchpad/run/all_findings.json`

- Findings with source-line context: `scratchpad/run/findings_ctx.json`

- Stratified sample (seed 20260919): `scratchpad/run/sample.json`, features: `scratchpad/run/sample_features.json`

- Final per-item classification: `scratchpad/run/final_classified.json`, tallies: `scratchpad/run/tallies.json`
