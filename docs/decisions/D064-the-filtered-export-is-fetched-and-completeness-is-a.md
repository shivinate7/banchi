## D64 — The Filtered Export is fetched, and completeness is a delta rather than a claim

**The last manual step in `runs -> join` is gone: the server downloads the export instead of the operator, and one press on `#/runs` fetches and joins.** Built 2026-08-30.

`identify` spawns detached (D33) and the three free steps are re-runnable, so the only thing left between a finished batch and a joined run was opening TCGplayer, pressing Export Filtered CSV, waiting, and uploading the file back. `POST /pipeline/runs/<name>/export` fetches it.

**One fetch answers for whatever product lines the portal's filter is set to, which may be several.** A file answers for the games its own `Product Line` cells claim, and D25 has always allowed two games to share one file.

**This entry said the opposite until the first live fetch, and the correction is the useful part.** It read that all eleven of the owner's historical exports carry a single product line, and concluded that a mixed-game run needs one fetch per game. The premise was true of those eleven files and was never a fact about the portal. Measured on the first authenticated fetch, 2026-08-30: 394 rows over six product lines, and `games_claimed` answered `pokemon`, `pokemon_code`, `riftbound` and `one_piece` from one file.

| product line | rows |
|---|---|
| Pokemon | 203 |
| Riftbound League of Legends Trading Card Game | 145 |
| One Piece Card Game | 42 |
| YuGiOh | 2 |
| Card Sleeves | 1 |
| Playmats | 1 |

**A generalization drawn from stored files rather than from the rule is what failed here.** D25 already decided this and the pipeline already handled it; the limitation existed only in this prose.

### What replaces the promise

**This process now holds a secret and opens a socket, and the sentence that said otherwise is rewritten rather than narrowed.** D33 already broke the money half of `capture_server.py`'s header. What survived was a file-boundary claim beside the import: no key, no socket, no child. `server/tcg_export.py` reads a TCGplayer session cookie from `.env` and opens a socket to `store.tcgplayer.com`.

**Narrowing it to "no socket to Anthropic" was available and is refused.** That is the drift D16 exists to catch.

What holds instead: one host, one method, one route, in one module with one caller, and it cannot cause a charge. `POST /pipeline/identify` is still the only route that can.

### The probe that would make this simpler is still open

**Every seller-admin route answers `302 -> /admin/account/logon` unauthenticated, before any parameter is read.**

| route | unauthenticated |
|---|---|
| `GET /Admin/Pricing/DownloadMyExportCSV` | 302 to logon |
| `GET /admin/pricing/getjsonfilters` | 302 to logon |
| `GET`/`POST /admin/pricing/productsearch` | 302 to logon |

This is cookie-session auth, not the order-management API, which is another host answering `www-authenticate: Bearer`. The two were conflated once while this was scoped and reached the wrong conclusion.

**Amended 2026-08-30: the `Bearer` half is measured false, and the sentence stands because the conflation it warns about was real.** The order host is a cookie session on the same `.tcgplayer.com` ticket this table's host uses; what does not transfer between the two is the body convention, not the auth. D69 has the capture.

**Whether export scope can be set by request is therefore unanswered.** It needs one authenticated probe, which needs the cookie, which only the owner can place. If scope can be set, the better design is to ask for a scoped export rather than inspect a broad one: fetch the sets the run needs with printings and conditions unfiltered, and the file is complete within scope by construction. That is recorded and not built, because a path that has never run must not carry a comment claiming a property nobody measured.

**Its scope source does not exist yet either, which is the second finding.** No identification profile returns a set. Measured across all four runs on disk: `pokemon_card_v1` answers `{name, number, printed_total, finish, confidence}` and `riftbound_card_v1` answers `{name, number, finish, confidence}`. `printed_total` is a denominator. The set is knowable only after a join, from the export's own `Set Name` column, which is circular for deciding what to fetch. `set_hint` is the only pre-join source and covers 676 of 715 cards; box 3 carries none and spans six Riftbound sets.

### Completeness cannot be read off an export

**Three filters narrow a Filtered Export independently, and one leaves no trace in the file.**

| axis | visible in the file |
|---|---|
| printings (All Printings off) | yes |
| condition | yes |
| listings with photos | no — `Photo URL` is empty in all eleven exports, filtered and unfiltered |

**The obvious guard fails because the axes are independent.** Refusing a file with no non-Near-Mint condition row passes an All-Printings-off export, which still carries every condition for the printings it does contain.

**What missing printings cost is a silent mislisting.** D3 rung 2 fires when exactly one condition row exists for a number, so a variant-thinned file manufactures single-row numbers and a reverse holo with no finish claim resolves to the normal row. A missing SKU is loud by comparison: the card queues as `no_catalog_row`.

### The guard

**Completeness against the catalog is unknowable; completeness against this run's own previous export is arithmetic.** Two readings, per game the fetch answers for.

- SKUs the baseline carried and this file does not.
- Numbers that had several finish rows and now have one. Counted over `condition_by_finish`'s own values, and keyed the way the row would be found: by `(Set Name, Number)` where there is a number, by name where there is not.

**One refusal code covers both, because a condition row is a SKU.** A number cannot lose a printing without losing the row that carried it, so a second code could never fire alone.

**`cli/resolve.py:exports_for` does the ruling, so the check is the real rule rather than a second approximation.** It runs over the fetched file plus whichever recorded exports it does not replace, before anything is joined. `games_claimed` is extracted from it for the one thing the route must know first.

**Two acknowledgements, each named for the fact it answers.** `accept_narrower` says the file covers less than the last one and the operator means it. `accept_unverified` says the run has nothing to compare against. Separate fields because one is evidence and the other is its absence.

**The first join of a run costs one acknowledgement and every re-join is autonomous.** `join` is free and routinely pointed at a refreshed export, which is where the fetch does its work and where a baseline exists.

### Both readings were wrong in the first build

**Measuring against the owner's real exports found two defects that a three-row fixture could not.** Both made the check look like it worked: one fired on everything, one on nothing.

**Play conditions are not finishes.** D12 scopes the product to Near Mint and the committed fixtures are Near-Mint-only; a wide export carries eleven to sixteen conditions because it also lists Lightly Played through Damaged. Measured on box 3's export against the wide Riftbound file: all 153 numbers read as thinned and **not one had lost a finish**. The refusal would have fired on an operator doing the right thing, carrying a sentence about mispricing that was false.

**The key carried `Product Name`, which loses real cases.** Finish variants usually share a product name, 143 of sv09's 144 multi-row numbers. Keyed `(set, number)` the wide Riftbound export has **550** numbers stocked in more than one finish; keyed with the name, **522**. Twenty-eight were invisible to the check written to find them.

**The guard does not fire on the owner's own refresh.** Run `2026-08-29-box1-01` holds two real exports taken four minutes apart, 60 rows then 2,008. It allows them. A guard that refused a legitimate widening would be read past rather than read.

### Three defects this branch found in itself

**A one-second filename stamp let a second fetch overwrite the export the run was joined against.** That file is the baseline the guard compares to, so the check then compared a file to itself and passed. The name carries a content digest now, and a refusal deletes only what the request created. T7 found it before the route had run for real.

**The remedy `tcg_session_expired` prints did not work.** It tells the operator to replace the value in `.env`, and `envfile.get` could not see them do it: `load` returns early once loaded, and it will not overwrite a name it set itself. Neither cache had mattered before, because an API key and a mirror path are placed before anything starts. A session expires, and D53's supervisor runs for days without watching `.env`. `envfile.get_live` reads the file fresh; `_from_file` keeps a real environment variable winning.

**The CSRF gate's stated reason was falsified by this branch.** `capture_server.py` justified the origin check with "there are no credentials in this product", which now understates what it guards: a page in another tab could otherwise make this server spend the owner's marketplace session. The conclusion is unchanged and the reason is corrected. T7 asserts the refusal lands before the cookie is read.

### What it costs

**The fetch composes with the recorded exports and `join` does not.** `exports_for` replaces the recorded mapping outright once any `--export` is passed, which the upload path has always done. So on a mixed-game run, fetching one game's file and joining with it alone passes the fetch and refuses at the join, naming the uncovered game. Making a recorded export compose with an explicit `--export` changes that function's contract and has not been argued. It is a narrower case than it looked when this was written: a fetch returns whatever product lines the portal's filter holds, and the measurement above shows that covering every game the run holds in one file is the ordinary state rather than the exception.

**The cookie is a bearer instrument and `.env` is the only place it lives.** Never logged, never in a refusal message, never written into a run directory; T7 asserts the last over every file the run holds. `PKMNSCAN_TCG_EXPORT_URL` refuses to carry it anywhere but https or loopback, because a knob that redirects a session cookie is an exfiltration channel wearing a test seam. One redirect hop is followed, and the cookie is not re-sent across a host change.

**What was fetched is downloadable.** `_artifacts` lists off the run directory, so the operator can open the file this route summarizes rather than trust the summary.

**The WAF does not block an authenticated stdlib client, measured 2026-08-30.** The owner placed a session cookie and the fetch returned 68,363 bytes over 394 rows. This was the one thing the entry recorded as owed, and it is the reason `PKMNSCAN_TCG_USER_AGENT` exists: the earlier unauthenticated measurement said nothing about a request carrying a session, so a block was a plausible outcome the build had to survive. It did not occur. `tcg_blocked` stays, because one measurement on one day is not a guarantee about a rule somebody else maintains.

**What that fetch also showed is that the portal's saved filter decides what arrives.** It returned the owner's current listings — eight conditions including `Unopened` and the Lightly Played family — rather than a catalog export. That is not a defect in the fetch, and the guard is what catches it: against box 3's baseline the same file carries 145 Riftbound rows to that run's 153, so it refuses `export_narrower` and names what went.

**Amended 2026-09-02: the delta guard is retired.** D65 met the condition above the same day and names the scope, so this guard's remedy asked about a Pricing-tab filter the request overrides. A run directory is new per run, so `previous is None` on every first fetch and `export_unverified` fired on every run — a 1.7 MB download unlinked and fetched again on a press; `export_narrower` fired on a legitimate set-scoped fetch after a category-wide one. Both codes, both fields, `_coverage`, `_printings` and `_finish_conditions` are gone; `export_scope_incomplete` is the whole guard; the receipt carries `previous`, the last joined export's file, rows and SKUs per game, and refuses nothing on it. The filename finds identical bytes by digest before it stamps — with the stamp first, every re-fetch added a copy, and `2026-08-31-box3-01` holds two byte-identical 366 KB exports 29 seconds apart.

**Amended 2026-09-11: `get_live` did not survive a spawn, and the key this entry judged non-rotating is what proved it.** Its docstring recorded `ANTHROPIC_API_KEY` as a value that "does not change under a running process". It expires. The owner's did, they pasted a new one into `.env`, and `./pkmnscan identify` and the `#/runs` press both kept sending the dead one — `make down` / `make up` was the only thing that picked it up, which is the restart D53 exists to remove.

**Two causes, and the obvious fix is only the first.** `identify/batch.py:_client` constructed `anthropic.Anthropic()` with no key and left the read to the SDK, so the value the process started with was the only one it could ever send; it resolves through `get_live` and passes the key explicitly now. And `get_live` was defeated one process down: `_from_file` is a process global, every child here is spawned with `dict(os.environ)`, and this supervisor reads ONE `.env` line (`PKMNSCAN_LAN_NAME`) while `load` lifts them all — so the capture server inherits a file value as a real environment variable and, correctly by `get_live`'s own rule, never reads the file again.

**Measured on the owner's machine the same day, from the initial environments `ps eww` reports rather than from `.env`**: the main checkout's capture server carried `ANTHROPIC_API_KEY`, `TCGPLAYER_STORE_COOKIE` and `PKMNSCAN_LAN_NAME`; the sibling checkout, which has no `.env`, carried none. **So the cookie fix this entry is about had the same defect**, and the remedy `tcg_session_expired` prints was as dead under the supervisor as the key's — the thing this entry says is worse than saying nothing.

`envfile.FROM_FILE_ENV` (`PKMNSCAN_ENV_FROM_FILE`) carries the lifted names across a spawn, **names only and never values**, adopted by `load` before it reads the file. The environment is still copied wholesale, because a child that did not inherit `PKMNSCAN_HOME` would run against another store (D43); what travels is the distinction, not a narrower copy. T7's `check_key_rotation` drives it through `_client` and through a real child process in a throwaway tree, and is mutation-tested on four arms — two of them the pre-fix reader, which go red on the assertion that names the rotation.

---
