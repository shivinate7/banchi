## DEBT78 — the merge flow belongs in claude-settings

By the owner's word, Banchi's merge flow moves up into claude-settings as a shared merge tool.
The flow claims numbers before merge. It waits for CI on the claim commit. On failure it reverts
the claim. Then it merges. Before-merge becomes the default for every repo.

**Why before-merge:** main never holds a slug, and a failed claim never reaches main.

**Upstream today:** claude-settings' `actions/stamp` stamps after merge, and only q_max uses it.

**Blocker, open:** the claude-settings README says `actions/` stops working for other repos
when claude-settings goes private.

**Stopgap:** `scripts/claim-ids.py` writes a gloss at a claimed cite's first use in CLAUDE.md
(`gloss_first_uses`), so the docs-audit `rule enforcement` row passes after a claim.

**Closes when:** the shared tool lands and Banchi calls it. Delete `entry_gloss` and
`gloss_first_uses` then.
