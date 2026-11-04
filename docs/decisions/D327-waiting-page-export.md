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
export script and no copy on main. A repo changes to fit a shared tool, never the tool to fit a
repo (owner ruling, via the coordinator).

- The copy is folder `waiting/` on the record branch `roadmap`, one file per document. Tools read
  the folder name through claude-settings `lint/layout.py`, never as a literal.
- The page's URL is the `waiting-page` key in `.claude/layout-extras.json`.
- Only triage writes the record branch (claude-settings decision roadmap-one-writer). A lane that
  must land the copy sends the files to triage.

**The writer reads the diff before it commits.** No pattern catches text the owner ruled out of the
repo, such as a closed item that restates a concern the owner asked to omit. The writer edits or
deletes that item on the page first. This repo is public.

**The shared scan has no address shapes.** It refuses tokens, keys, cookies, auth headers,
passwords, email addresses and phone numbers. A street address, a PO box and a city, state and ZIP
line pass it (DEBT114, the waiting-page scan misses address shapes). The writer's read of the diff
is the cover until the shared scan refuses them.

**Reopen** if the waiting page gains an API a script can call.
