23. ~~**The number is claimed at the merge, not guessed on the
    branch**~~ — **done 2026-09-11.** D140, amending D72 and D80. A branch
    writes its entry's heading as a slug and cites it; `scripts/claim-ids.py` allocates `max + 1`
    against main inside `make merge`, commits the substitution to the pull request's
    branch, waits for that commit's checks, and only then merges. All three id
    namespaces: decisions, the code-card track's `C` entries, and this list. It
    retired `renumbered ids` and `vacated ids`, which repaired a renumber rather than
    preventing one. **This item's own marker is `0.` because its number is not
    allocated yet** — markdown has no ordered-list marker that can hold a slug, so the
    claim rewrites the marker and the token together.
