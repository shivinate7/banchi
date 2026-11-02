# D-waiting-page-export — The waiting page's data is a committed record

The page writer exports the waiting page's database to `docs/waiting/` at each wake, so any account can read it.

Kind: process
Home: scripts/waiting-export.py

**Why.** The waiting page's items, answers and groups lived only in the artifact's database. When
the page moved to another account, Claude Code could not read that database, and the items were
rebuilt from transcripts. The repo held no copy. The owner asked for one.

**The duty.** The page writer (`meta.page.writer`, the coordinator) exports the page's data to
the records folder at each wake, and before any republish. It is a read on demand inside a wake
already running: no timer, no watcher.

1. `python3 scripts/waiting-export.py --calls` prints the page URL, from the `waiting-page` key in
   `.claude/layout-extras.json`, and the four collections.
2. The writer reads `items`, `answers`, `groups` and `meta` with ArtifactData `list`, `query.limit`
   1000 and `out_dir`, into one fresh, empty scratch folder. It pages with `next_cursor` until none
   comes back. A reused folder keeps a deleted item's old file, so the folder is always new.
3. `python3 scripts/waiting-export.py <folder>` scans, then writes `docs/waiting/`. It prints
   `unchanged` or the files it changed.
4. Only when it changed files, the writer commits them on a branch and hands that branch to the
   batch runner like any lane. Main moves by pull request (D42, main moves by pull request).

**Two halves, because a script cannot read the database.** ArtifactData is a Claude tool call, not
an API a script can reach. So Claude reads, and the script normalizes and scans. The script sorts
keys and writes fixed indentation, so an unchanged page makes no diff.

**The scan.** This repo is public. Before it writes, the script scans every key and string for
tokens (GitHub, Anthropic and other `sk-` keys, AWS, Slack, JWT, bearer), private keys, password or
key values, cookies, email addresses, phone numbers and street addresses. A hit writes nothing and
names the kind and the field, never the text. The writer removes it from the page and reads again.
`make waiting-export-selftest` proves the scan red on each fake kind and green on a clean export.
**NOT MECHANIZED:** a buyer's name with no address beside it. A pattern cannot tell a buyer's name
from a card's name. The writer reads the diff before each commit, as the public-repo rule says.

**Not exported.** `receipts/` (when a session read and filed an answer) and the page's designs and
roadmap block, which live in the page itself. The answers and items carry the rulings; the receipts
only time their filing.

**Reopen** if the waiting page gains an API a script can call, or if the scan stops a clean export
twice: a guard that cries wolf is spent.
