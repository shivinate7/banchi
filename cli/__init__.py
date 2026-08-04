"""The four commands. Wiring only — every rule they enforce lives somewhere testable.

    pkmnscan identify   <capture-dir>                 submit, wait, collect, cache. Costs money.
    pkmnscan join       <run-dir>                     resolve against the export. Free.
    pkmnscan emit       <run-dir>                     write import CSVs. Free.
    pkmnscan reconcile  <run-dir> <staged-export.csv> confirm what TCGplayer actually staged.

FOUR COMMANDS, NOT ONE. A batch takes minutes to hours and the pricing decision needs a
human, so one blocking command would put a person in the middle of a poll loop. Each is
independently resumable and re-runnable, and `join` and `emit` cost nothing — so re-running
them after clearing a review or changing a price is free, which is what makes it reasonable
to insist the decision be made rather than defaulted.

LOGIC LIVES ELSEWHERE. `pipeline/`, `identify/`, `geometry/` and `store/` hold the rules;
the harness tests those. This package parses arguments, prints, and sequences. If a rule
worth testing appears in here, it is in the wrong file — the same reason
`pipeline/__init__.py` gives for the pipeline not living inside `harness/`.
"""
