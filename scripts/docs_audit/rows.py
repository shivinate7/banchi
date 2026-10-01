"""The rows: `ROWS` names every check, its tier and its arguments, and `audit()` runs them."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Set, Tuple

from .code_invariants import (
    check_claim_clients,
    check_claim_decode,
    check_column_counts,
    check_dist_path_agreement,
    check_error_words,
    check_estimate_wire,
    check_identity_writers,
    check_import_filename_agreement,
    check_import_layering,
    check_server_concurrency,
    check_sole_reader,
    check_threshold_agreement,
    check_unscoped_walk,
)
from .core import Report, enter_staged_mode, markdown_files, rel, staged_changes
from .design import (
    check_breakpoint_columns,
    check_breakpoints,
    check_design_tokens,
    check_js_breakpoints,
    check_raw_color,
    check_raw_motion,
)
from .dispatch import check_coupling, check_dispatch, check_subject_counts
from .env_map import (
    check_build_order_mirror,
    check_codex_hooks,
    check_env_vocabulary,
    check_hatch_state,
    check_hook_roster,
    check_map,
    check_map_sections,
    check_subagent_override,
)
from .games import (
    check_game_coverage,
    check_game_vocabulary,
    check_join_key_shape,
    check_matrix_superset,
)
from .harness_criteria import (
    check_criteria_evidence,
    check_evidence_freshness,
    check_harness_tests,
    check_pass_criteria,
)
from .hygiene import (
    check_agent_links,
    check_design_check_verdict,
    check_doc_hygiene,
    check_positional_references,
    check_recorded_deletions,
    check_route_rosters,
    check_spec_seal,
    check_test_purposes,
)
from .paths_commands import (
    check_allowlist,
    check_commands_roster,
    check_line_anchors,
    check_make_targets,
    check_paths,
    check_pkmnscan_commands,
    code_files,
    load_allowlist,
)
from .reasons import (
    check_export_request,
    check_hint_reasons,
    check_motion_params,
    check_supervisor_self_watch,
    check_transport_promise,
)
from .records import (
    check_claim_vocabulary,
    check_debt_ids,
    check_debt_index,
    check_debts_headings,
    check_decision_ids,
    check_decision_structure,
    check_id_claims,
    check_numbered_record_growth,
)
from .registry_scopes import (
    check_audit_invocation,
    check_browser_scope,
    check_check_registry,
    check_commit_path,
    check_guard_scope,
    check_serve_scope,
    check_spec_map,
    check_suite_lock,
)
from .rules import check_identifier_spelling, check_rule_enforcement
from .screens import check_logo, check_storage_keys
from .spelling import check_shell_substitution
from .stability import check_font_stability, check_layout_transitions, check_scrollbar_gutter, check_state_layout
from .status_reach import check_closed_vocabularies, check_status_sources, check_tested_by_reach
from .strings import check_no_mechanism_on_screen, check_typed_interpunct, check_views_opsec

# ------------------------------------------------------------------------------ main

# THE TIER, per row (owner's ruling on Q1, test-audit-2026-09-27 TIERS, applied by L12,
# 2026-09-28). Three tiers, read straight into the dispatch below rather than restated as a
# second list somewhere else:
#
#   TIER 1  blocks at commit. Fast, and a wrong reference sends a reader to the wrong
#           command, path, route or target.
#   TIER 2  blocks in CI, never at commit. Keeps two artifacts, rosters or registries
#           agreeing with each other; main must stay coherent, a commit need not wait.
#   TIER 3  a note printed once in CI, never blocking. Style or prose; already ADVISORY.
#
# A ROW CANNOT BE UNTIERED: the tier is a field of `AuditRow`, so a row added to `ROWS` names
# one or fails to build. The old dict defaulted a row it did not name to Tier 1, and nothing
# caught a row someone forgot to tier; the table closes that. A merged family (M3, L8) is one
# check under several names and takes the HIGHEST tier of its parts (never quieter than its
# loudest member, `_merge_rows`'s own rule, applied to blocking speed instead of severity):
# `logo` folds in `mac icon grid`, ruled Tier 2 on its own, but the family is Tier 1 because
# four of its five parts are. `env vocabulary`, `column counts` and `closed vocabularies` are
# each Tier 1 because every part they fold was Tier 1. A check that carries two names is two
# entries with the same function, and it runs once when either name's tier runs.


class AuditRow(NamedTuple):
    """One row of the audit: its name, its tier, the check that emits it and what it is given.

    `args` names what `Context` supplies after the report, in call order. `staged_only` rows run
    only under `--staged`.
    """

    name: str
    tier: int
    check: Callable[..., None]
    args: Tuple[str, ...] = ()
    staged_only: bool = False


class Context:
    """What one audit run hands its rows: the report and the tree's answers, computed once."""

    def __init__(self, report: Report, staged_only: bool) -> None:
        self.report = report
        self.staged_only = staged_only
        # Mode first, and before anything reads or enumerates. Everything below (the
        # allowlist, the markdown list, every existence check inside every check) has to be
        # answered about ONE tree, and in staged mode that tree is the index. Loading any of
        # it beforehand silently mixes the worktree back in.
        if staged_only:
            enter_staged_mode()
        self.allowed = load_allowlist()
        self.all_docs = markdown_files()
        self.staged: Set[str] = set(staged_changes()) if staged_only else set()
        self.docs = [doc for doc in self.all_docs if rel(doc) in self.staged] if staged_only else self.all_docs

    @cached_property
    def staged_code(self) -> List[Path]:
        code = code_files()
        return [f for f in code if rel(f) in self.staged] if self.staged_only else code


ROWS: Tuple[AuditRow, ...] = (
    AuditRow("paths", 2, check_paths, ("docs", "allowed")),
    AuditRow("allowlist", 1, check_allowlist, ("allowed",)),
    AuditRow("line anchors", 1, check_line_anchors, ("docs", "staged_code")),
    AuditRow("make targets", 1, check_make_targets, ("docs",)),
    AuditRow("commands roster", 1, check_commands_roster, ()),
    AuditRow("pkmnscan commands", 1, check_pkmnscan_commands, ("docs", "all_docs")),
    AuditRow("harness tests", 1, check_harness_tests, ("docs", "allowed")),
    AuditRow("pass criteria", 2, check_pass_criteria, ()),
    AuditRow("criteria evidence", 2, check_criteria_evidence, ()),
    AuditRow("evidence freshness", 3, check_evidence_freshness, ("staged_only",)),
    AuditRow("decision ids", 1, check_decision_ids, ("docs",)),
    AuditRow("decision structure", 1, check_decision_structure, ()),
    AuditRow("id claims", 1, check_id_claims, ()),
    AuditRow("numbered record growth", 1, check_numbered_record_growth, ("staged_only",)),
    AuditRow("claim vocabulary", 1, check_claim_vocabulary, ()),
    AuditRow("debts headings", 1, check_debts_headings, ()),
    AuditRow("debt index", 1, check_debt_index, ()),
    AuditRow("debt ids", 1, check_debt_ids, ("docs",)),
    AuditRow("env vocabulary", 1, check_env_vocabulary, ("docs", "allowed")),
    AuditRow("hatch state", 3, check_hatch_state, ()),
    AuditRow("subagent override", 1, check_subagent_override, ()),
    AuditRow("claim decode", 1, check_claim_decode, ()),
    AuditRow("claim clients", 1, check_claim_clients, ()),
    AuditRow("sole reader", 1, check_sole_reader, ()),
    AuditRow("server concurrency", 1, check_server_concurrency, ()),
    AuditRow("estimate wire", 1, check_estimate_wire, ()),
    AuditRow("column counts", 1, check_column_counts, ()),
    AuditRow("threshold agreement", 1, check_threshold_agreement, ()),
    AuditRow("dist path agreement", 1, check_dist_path_agreement, ()),
    AuditRow("import filename agreement", 1, check_import_filename_agreement, ()),
    AuditRow("repo map", 1, check_map, ("allowed",)),
    AuditRow("hook roster", 2, check_hook_roster, ()),
    AuditRow("codex hooks", 2, check_codex_hooks, ()),
    AuditRow("map sections", 3, check_map_sections, ()),
    AuditRow("build order mirror", 2, check_build_order_mirror, ()),
    AuditRow("game vocabulary", 1, check_game_vocabulary, ()),
    AuditRow("game coverage", 3, check_game_coverage, ()),
    AuditRow("game coverage allowlist", 3, check_game_coverage, ()),
    AuditRow("matrix superset", 1, check_matrix_superset, ()),
    AuditRow("join key shape", 1, check_join_key_shape, ()),
    AuditRow("closed vocabularies", 1, check_closed_vocabularies, ()),
    AuditRow("supervisor self-watch", 1, check_supervisor_self_watch, ()),
    AuditRow("motion params", 1, check_motion_params, ()),
    AuditRow("logo", 1, check_logo, ()),
    AuditRow("export request", 1, check_export_request, ()),
    AuditRow("transport promise", 1, check_transport_promise, ()),
    AuditRow("hint reasons", 1, check_hint_reasons, ()),
    AuditRow("tested_by reach", 2, check_tested_by_reach, ()),
    AuditRow("status sources", 2, check_status_sources, ()),
    AuditRow("design tokens", 1, check_design_tokens, ()),
    AuditRow("raw color", 1, check_raw_color, ()),
    AuditRow("raw motion", 1, check_raw_motion, ()),
    AuditRow("scrollbar gutter", 1, check_scrollbar_gutter, ()),
    AuditRow("font stability", 1, check_font_stability, ()),
    AuditRow("layout transitions", 1, check_layout_transitions, ()),
    AuditRow("state layout", 1, check_state_layout, ()),
    AuditRow("breakpoints", 1, check_breakpoints, ()),
    AuditRow("breakpoint columns", 3, check_breakpoint_columns, ()),
    AuditRow("js breakpoints", 1, check_js_breakpoints, ()),
    AuditRow("storage keys", 1, check_storage_keys, ()),
    AuditRow("views opsec", 1, check_views_opsec, ()),
    AuditRow("views exposure", 1, check_views_opsec, ()),
    AuditRow("doc hygiene", 3, check_doc_hygiene, ("docs",)),
    AuditRow("route rosters", 2, check_route_rosters, ()),
    AuditRow("agent links", 1, check_agent_links, ()),
    AuditRow("test purposes", 2, check_test_purposes, ()),
    AuditRow("recorded deletions", 1, check_recorded_deletions, ()),
    AuditRow("spec seal", 1, check_spec_seal, ()),
    AuditRow("verdict file", 2, check_design_check_verdict, ()),
    AuditRow("check registry", 2, check_check_registry, ()),
    AuditRow("commit path", 2, check_commit_path, ()),
    AuditRow("no mechanism on screen", 1, check_no_mechanism_on_screen, ()),
    AuditRow("typed interpunct", 1, check_typed_interpunct, ()),
    AuditRow("suite lock", 2, check_suite_lock, ()),
    AuditRow("browser scope", 1, check_browser_scope, ()),
    AuditRow("spec map", 2, check_spec_map, ()),
    AuditRow("serve scope", 1, check_serve_scope, ()),
    AuditRow("guard scope", 1, check_guard_scope, ()),
    AuditRow("check numbering", 2, check_positional_references, ("docs",)),
    AuditRow("numbering in code", 3, check_positional_references, ("docs",)),
    AuditRow("audit invocation", 2, check_audit_invocation, ()),
    AuditRow("identifier spelling", 3, check_identifier_spelling, ()),
    AuditRow("shell substitution", 1, check_shell_substitution, ()),
    AuditRow("unscoped walk", 1, check_unscoped_walk, ()),
    AuditRow("import layering", 1, check_import_layering, ()),
    AuditRow("error words", 1, check_error_words, ()),
    AuditRow("identity writers", 1, check_identity_writers, ()),
    AuditRow("rule enforcement", 2, check_rule_enforcement, ()),
    # Last but two, and it is the row that says the rows above are all of them. It
    # reconciles the check functions the package defines against the ones this table names.
    #
    # IT DOES NOT ANSWER FOR ITSELF. Delete this one line and every other row still prints
    # green, the run exits 0, and the `check dispatch` row is simply absent, which is the exact
    # silent shrinkage the row exists to catch, one level up. A detector cannot detect its own
    # absence, and no reconciliation added here can close it, because the reconciler would need
    # the same single entry nothing vouches for. What catches it is `--self-test`, whose last
    # case calls `check_dispatch()` directly and asserts the table names every check, and
    # `--self-test` runs by hand, on no gate. So this line is the root of the recursion:
    # unwiring anything else fails the commit, and unwiring THIS fails nothing automatic.
    # docs/debts/ records it under the entry that shipped the row; do not delete it on the
    # strength of the audit staying green.
    #
    # TIER 2: `check_dispatch` reads the package's own source with `ast`, not the tree it
    # audits, so it costs the same in commit and CI mode and gates nothing that a session
    # edits. Skipping it at commit only delays catching an unwired check until CI, never lets
    # one ship unnoticed to main.
    AuditRow("check dispatch", 2, check_dispatch, ()),
    AuditRow("coupling", 3, check_coupling, (), staged_only=True),
    # AFTER EVERYTHING, because its subject is the other rows' subject counts, including
    # `coupling`, which only exists in staged mode. It is the one row that must see the whole
    # report, so it is the one row that cannot be anywhere but here.
    AuditRow("subject counts", 2, check_subject_counts, ("staged_only",)),
)

TIER: Dict[str, int] = {row.name: row.tier for row in ROWS}


def _runs(tier: int, commit_only: bool) -> bool:
    """Whether a row of this tier runs, given the mode.

    A Tier 1 row always runs. A Tier 2 or 3 row is SKIPPED ENTIRELY in commit mode, never
    computed and never printed, which is where the pre-commit hook's own time comes back
    (`paths` alone measured 5.95s; `identifier spelling`, 5.91s). In full/CI mode nothing is
    skipped, so a Tier 2 row still blocks CI and a Tier 3 row still prints, exactly as
    `ADVISORY`/`MECHANICAL` already decide.
    """
    return (not commit_only) or tier <= 1


def audit(staged_only: bool, commit_only: bool = False) -> Report:
    context = Context(Report(), staged_only)
    ran: Set[Callable[..., None]] = set()
    for row in ROWS:
        if row.staged_only and not staged_only:
            continue
        if not _runs(row.tier, commit_only) or row.check in ran:
            continue
        ran.add(row.check)
        row.check(context.report, *(getattr(context, name) for name in row.args))
    return context.report
