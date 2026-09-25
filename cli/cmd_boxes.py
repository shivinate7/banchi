"""`pkmnscan boxes names` — give every unnamed box its stored name. Previews by default.

THE OWNER'S RULING, 2026-09-23 (D-a-box-is-shown-by-its-name): a box is shown by its name
only, and the box number stays inside the store. A new box with no name gets a stored default
name at creation (`store/master.py:Inventory.default_box_name`). This command is the one-time
backfill for the boxes that were created before that rule: each gets `Box <number>`, today's
number, so nothing visible changes and the physical labels on the drawers still match.

PREVIEW FIRST, AND THE WRITE IS ONE TRANSACTION. With no flag the command reads the store and
prints the plan. `--write` computes the plan again INSIDE the store lock and applies it in one
`Store().write()` transaction, so a box renamed between the preview and the write keeps its
new name. A second `--write` plans nothing: a box with a name is never touched.
"""

from __future__ import annotations

from store.session import Store


def _names(args, say) -> int:
    write = bool(getattr(args, "write", False))

    plan = Store().read().inventory.box_name_plan()
    say("BOX NAMES -> every box with no name gets the stored name `Box <number>`")
    say(f"  {'WRITING' if write else 'PREVIEW, nothing will be written'}")
    if not plan:
        say("  Every box already has a name. Nothing to do.")
        return 0
    for number, name in plan:
        say(f"    box {number} -> {name}")

    if not write:
        say("")
        say(f"  {len(plan)} box(es) would get a name. Re-run with --write to apply.")
        return 0

    with Store().write() as snapshot:
        written = snapshot.inventory.backfill_box_names()
    say("")
    say(f"  WROTE {len(written)} box name(s).")
    return 0


_SUBCOMMANDS = {
    "names": _names,
}


def run(args, say) -> int:
    handler = _SUBCOMMANDS.get(getattr(args, "boxes_action", None))
    if handler is None:
        say("pkmnscan boxes <names>")
        return 2
    return handler(args, say)
