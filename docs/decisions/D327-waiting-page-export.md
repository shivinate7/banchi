# D327 — The waiting page's data is a committed record

The page writer copies the waiting page's database to folder `waiting/` on the record branch, with the shared waiting-page tool.

Kind: process
Home: .claude/layout-extras.json

**Why.** The waiting page's items, answers and groups lived only in the artifact's database. When
the page moved to another account, Claude Code could not read that database, and the items were
rebuilt from transcripts. The repo held no copy. The owner asked for one.

**The duty is the shared one.** claude-settings decision waiting-data-in-repo (a copy of the
waiting page lives in the repo) sets the copy's home, its file layout and its scan. The skill
`waiting-page`, section "Keep a copy in the repo", holds the writer's steps. Banchi keeps no
export script, and main's tip holds no copy. The old copy on main stays in git history. The
shared scan finds nothing in it. A repo changes to fit a shared tool, never the tool to fit a repo
(owner ruling, via the coordinator).

- The copy is folder `waiting/` on the record branch `roadmap`, one file per document. Tools read
  the folder name through claude-settings `lint/layout.py`, never as a literal.
- The page's URL is the `waiting-page` key in `.claude/layout-extras.json`.
- Only triage writes the record branch (claude-settings guard rule roadmap-one-writer, in decision
  session-tiers). A lane never runs the export.

**The writer reads the diff before it commits.** This repo is public. No pattern catches text the
owner ruled out of the repo, such as a closed item that restates a concern the owner asked to omit.
The writer edits or deletes that item on the page first.
**NOT MECHANIZED:** a buyer's name with no address beside it. A pattern cannot tell a buyer's name
from a card's name.

**The shared scan misses shapes banchi's old scan refused.** It refuses tokens and keys of known
shapes, `Cookie:` headers, auth headers, passwords, email addresses and phone numbers. DEBT114 (the
waiting-page scan misses address and credential-name shapes) lists what passes it: addresses, a
`NAME=value` or `name: value` line whose name ends in key, secret, token or cookie and whose value
has no known token shape, bare cookies, and a bare `Bearer` or `Basic` value. The writer's read of the diff is the cover until the shared scan refuses them.

**Not exported.** `receipts/` (when a session read and filed an answer) and the page's roadmap
block. The mockups' design data is exported, as `waiting/page/designData.json`. The answers and
items carry the rulings; the receipts only time their filing.

**Reopen** if the waiting page gains an API a script can call.
