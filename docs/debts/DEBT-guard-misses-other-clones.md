## DEBT-guard-misses-other-clones — Claude Code's Bash and Edit calls may reach a separate clone unrefused

**What.** For Claude Code, the shared guard's other-checkout rule judges only checkouts of this clone, so a `cd` into a separate clone, a write into one, and any write while the cwd sits in one all pass.

- **Before:** Banchi's tree clause (`scripts/guard-shell.py`, `clause_tree_bash`) refused all three. Claude Code now skips that clause (D179, shell mistakes are refused by resolving). Codex still runs it.
- **Seen here:** the lane session that cut the clause typed `cd /root/claude-settings` once, by habit, and Banchi's clause refused it. A write there would land in the shared settings checkout.
- **Ruled:** the owner ruled the skip (owner, 2026-10-28 12:49 CDT, waiting page item 41 a), and the `cd` refusal for this clone only (owner, 2026-11-01 17:25 CST, waiting page item 143 b). Neither names a separate clone. The shared guard's record calls this its ceiling (claude-settings decision an-agent-outside-its-home-tree-must-stop, "Outside the clone passes").
- **Not fixed because** the fix belongs to the shared guard in claude-settings, and the owner has not asked for it.
- **Closes when** the shared guard refuses a `cd` or a write into a separate clone, or the owner rules the gap accepted.
- **Points to** D179, D135 (Codex reads the same rules).

**Outcome at risk.** A write lands in another repository's checkout, such as the shared settings clone, with no refusal. Frequency is unmeasured.
