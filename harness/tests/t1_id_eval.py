"""T1 — Ground-truth ID eval.

Download ~50 official card images from pokemontcg.io across 2-3 sets as labeled fixtures
(the API record IS the label). Run identification against them. Report accuracy per set
and overall.

To implement:
  - Cache images under harness/images/ (gitignored — they are reproducible from the API).
  - Identification runs through the Batch API, model claude-haiku-4-5-20251001, not
    sequential calls. See CLAUDE.md.
  - Rerun after any prompt change. Write the score to harness/results/ and commit it, so
    a regression shows up in the diff rather than in a memory of last week's number.

Known blind spot (docs/GATES.md): official API images show no foil texture, so T1 cannot
validate the `finish` field. That is Gate B's job, against real photos. A green T1 must
never be read as variant detection working.

If overall_accuracy < 0.95, build-order step 4 applies: hand-feed the same 50 images
through TCGplayer Scan & Identify as a manual benchmark before tuning further. No
integration code either way — see D2 in docs/DECISIONS.md.
"""

from harness.tests import NotImplementedYet, Result

NAME = "T1"
DESCRIPTION = "Ground-truth ID eval against pokemontcg.io images"
PASS_CRITERIA = "overall_accuracy >= 0.95"

ID_ACCURACY_FLOOR = 0.95
EVAL_SET_COUNT = (2, 3)
EVAL_IMAGE_TARGET = 50


def run() -> Result:
    raise NotImplementedYet(
        "NOT_IMPLEMENTED: no identification pipeline yet (build-order step 5)"
    )
