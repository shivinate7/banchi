"""The rows: TIER, the mode filter and `audit()`, which runs every check."""

from __future__ import annotations

from typing import Dict

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
# A row this dict does not name is TIER 1 by default (`TIER.get(name, 1)`) — an added row
# blocks at commit until someone tiers it down, never the other way around. A merged
# family (M3, L8) takes the HIGHEST tier of its parts (never quieter than its loudest
# member, `_merge_rows`'s own rule, applied to blocking speed instead of severity): `logo`
# folds in `mac icon grid`, ruled Tier 2 on its own, but the family is Tier 1 because four
# of its five parts are. `env vocabulary`, `column counts` and `closed vocabularies` are
# each Tier 1 because every part they fold was Tier 1.
TIER: Dict[str, int] = {
    "paths": 2,
    "allowlist": 1,
    "line anchors": 1,
    "make targets": 1,
    "commands roster": 1,
    "pkmnscan commands": 1,
    "harness tests": 1,
    "pass criteria": 2,
    "criteria evidence": 2,
    "evidence freshness": 3,
    "decision ids": 1,
    "decision structure": 1,
    "id claims": 1,
    "numbered record growth": 1,
    "claim vocabulary": 1,
    "debts headings": 1,
    "debt index": 1,
    "debt ids": 1,
    "env vocabulary": 1,
    "hatch state": 3,
    "subagent override": 1,
    "claim decode": 1,
    "claim clients": 1,
    "sole reader": 1,
    "server concurrency": 1,
    "estimate wire": 1,
    "column counts": 1,
    "threshold agreement": 1,
    "dist path agreement": 1,
    "import filename agreement": 1,
    "repo map": 1,
    "hook roster": 2,
    "codex hooks": 2,
    "map sections": 3,
    "build order mirror": 2,
    "game vocabulary": 1,
    "game coverage": 3,
    "game coverage allowlist": 3,
    "matrix superset": 1,
    "join key shape": 1,
    "closed vocabularies": 1,
    "supervisor self-watch": 1,
    "motion params": 1,
    "logo": 1,
    "export request": 1,
    "transport promise": 1,
    "hint reasons": 1,
    "tested_by reach": 2,
    "status sources": 2,
    "design tokens": 1,
    "raw color": 1,
    "breakpoints": 1,
    "breakpoint columns": 3,
    "js breakpoints": 1,
    "storage keys": 1,
    "views opsec": 1,
    "views exposure": 1,
    "doc hygiene": 3,
    "route rosters": 2,
    "recorded deletions": 1,
    "test purposes": 2,
    "spec seal": 1,
    "verdict file": 2,
    "check registry": 2,
    "commit path": 2,
    "no mechanism on screen": 1,
    "typed interpunct": 1,
    "suite lock": 2,
    "browser scope": 1,
    "spec map": 2,
    "serve scope": 1,
    "guard scope": 1,
    "check numbering": 2,
    "numbering in code": 3,
    "audit invocation": 2,
    "identifier spelling": 3,
    "shell substitution": 1,
    "unscoped walk": 1,
    "import layering": 1,
    "error words": 1,
    "identity writers": 1,
    "rule enforcement": 2,
    "check dispatch": 2,
    "subject counts": 2,
    "coupling": 3,
}


def _run_at_commit(name: str, commit_only: bool) -> bool:
    """Whether a row of this name runs, given the mode.

    A Tier 1 row always runs. A Tier 2 or 3 row is SKIPPED ENTIRELY in commit mode — never
    computed, never printed — which is where the pre-commit hook's own time comes back
    (`paths` alone measured 5.95s; `identifier spelling`, 5.91s). In full/CI mode nothing is
    skipped, so a Tier 2 row still blocks CI and a Tier 3 row still prints, exactly as
    `ADVISORY`/`MECHANICAL` already decide. `commit_only=False` is the unconditional True
    this file ran with for every row before L12.

    A NAME MISSING FROM `TIER` DEFAULTS TO TIER 1, NEVER TO A SKIP. `TIER.get(name, 1)`
    reads 1 for anything the dict does not name, so a row added later and never tiered
    blocks at commit exactly as it would have before this file had tiers at all — the
    fail-loud choice, on `subject counts`'s own precedent (a row with no declared subject
    is a failure, never a silent pass). The alternative, defaulting an untiered row to skip
    at commit, would make forgetting to tier a new row the same shape as the defect L12
    exists to fix: a check nobody notices has stopped running. `check_dispatch` catches an
    UNDISPATCHED row; nothing yet catches an UNTIERED one, so the safe default carries the
    whole weight until a `tier census` row (or similar) is worth building.
    """
    return (not commit_only) or TIER.get(name, 1) <= 1


def audit(staged_only: bool, commit_only: bool = False) -> Report:
    report = Report()
    # Mode first, and before anything reads or enumerates. Everything below — the
    # allowlist, the markdown list, every existence check inside every check — has to be
    # answered about ONE tree, and in staged mode that tree is the index. Loading any of
    # it beforehand silently mixes the worktree back in.
    if staged_only:
        enter_staged_mode()
    allowed = load_allowlist()
    all_docs = markdown_files()
    docs = all_docs
    if staged_only:
        staged = set(staged_changes())
        docs = [doc for doc in all_docs if rel(doc) in staged]

    if _run_at_commit("paths", commit_only):
        check_paths(report, docs, allowed)
    if _run_at_commit("allowlist", commit_only):
        check_allowlist(report, allowed)
    if _run_at_commit("line anchors", commit_only):
        staged_code = code_files()
        if staged_only:
            staged_code = [f for f in staged_code if rel(f) in staged]
        check_line_anchors(report, docs, staged_code)
    if _run_at_commit("make targets", commit_only):
        check_make_targets(report, docs)
    if _run_at_commit("commands roster", commit_only):
        check_commands_roster(report)
    if _run_at_commit("pkmnscan commands", commit_only):
        check_pkmnscan_commands(report, docs, all_docs)
    if _run_at_commit("harness tests", commit_only):
        check_harness_tests(report, docs, allowed)
    if _run_at_commit("pass criteria", commit_only):
        check_pass_criteria(report)
    if _run_at_commit("criteria evidence", commit_only):
        check_criteria_evidence(report)
    if _run_at_commit("evidence freshness", commit_only):
        check_evidence_freshness(report, staged_only)
    if _run_at_commit("decision ids", commit_only):
        check_decision_ids(report, docs)
    if _run_at_commit("decision structure", commit_only):
        check_decision_structure(report)
    if _run_at_commit("id claims", commit_only):
        check_id_claims(report)
    if _run_at_commit("numbered record growth", commit_only):
        check_numbered_record_growth(report, staged_only)
    if _run_at_commit("claim vocabulary", commit_only):
        check_claim_vocabulary(report)
    if _run_at_commit("debts headings", commit_only):
        check_debts_headings(report)
    if _run_at_commit("debt index", commit_only):
        check_debt_index(report)
    if _run_at_commit("debt ids", commit_only):
        check_debt_ids(report, docs)
    if _run_at_commit("env vocabulary", commit_only):
        check_env_vocabulary(report, docs, allowed)
    if _run_at_commit("hatch state", commit_only):
        check_hatch_state(report)
    if _run_at_commit("subagent override", commit_only):
        check_subagent_override(report)
    if _run_at_commit("claim decode", commit_only):
        check_claim_decode(report)
    if _run_at_commit("claim clients", commit_only):
        check_claim_clients(report)
    if _run_at_commit("sole reader", commit_only):
        check_sole_reader(report)
    if _run_at_commit("server concurrency", commit_only):
        check_server_concurrency(report)
    if _run_at_commit("estimate wire", commit_only):
        check_estimate_wire(report)
    if _run_at_commit("column counts", commit_only):
        check_column_counts(report)
    if _run_at_commit("threshold agreement", commit_only):
        check_threshold_agreement(report)
    if _run_at_commit("dist path agreement", commit_only):
        check_dist_path_agreement(report)
    if _run_at_commit("import filename agreement", commit_only):
        check_import_filename_agreement(report)
    if _run_at_commit("repo map", commit_only):
        check_map(report, allowed)
    if _run_at_commit("hook roster", commit_only):
        check_hook_roster(report)
    if _run_at_commit("codex hooks", commit_only):
        check_codex_hooks(report)
    if _run_at_commit("map sections", commit_only):
        check_map_sections(report)
    if _run_at_commit("build order mirror", commit_only):
        check_build_order_mirror(report)
    if _run_at_commit("game vocabulary", commit_only):
        check_game_vocabulary(report)
    if _run_at_commit("game coverage", commit_only) or _run_at_commit("game coverage allowlist", commit_only):
        check_game_coverage(report)
    if _run_at_commit("matrix superset", commit_only):
        check_matrix_superset(report)
    if _run_at_commit("join key shape", commit_only):
        check_join_key_shape(report)
    if _run_at_commit("closed vocabularies", commit_only):
        check_closed_vocabularies(report)
    if _run_at_commit("supervisor self-watch", commit_only):
        check_supervisor_self_watch(report)
    if _run_at_commit("motion params", commit_only):
        check_motion_params(report)
    if _run_at_commit("logo", commit_only):
        check_logo(report)

    if _run_at_commit("export request", commit_only):
        check_export_request(report)
    if _run_at_commit("transport promise", commit_only):
        check_transport_promise(report)
    if _run_at_commit("hint reasons", commit_only):
        check_hint_reasons(report)
    if _run_at_commit("tested_by reach", commit_only):
        check_tested_by_reach(report)
    if _run_at_commit("status sources", commit_only):
        check_status_sources(report)
    if _run_at_commit("design tokens", commit_only):
        check_design_tokens(report)
    if _run_at_commit("raw color", commit_only):
        check_raw_color(report)
    if _run_at_commit("breakpoints", commit_only):
        check_breakpoints(report)
    if _run_at_commit("breakpoint columns", commit_only):
        check_breakpoint_columns(report)
    if _run_at_commit("js breakpoints", commit_only):
        check_js_breakpoints(report)
    if _run_at_commit("storage keys", commit_only):
        check_storage_keys(report)
    if _run_at_commit("views opsec", commit_only) or _run_at_commit("views exposure", commit_only):
        check_views_opsec(report)
    if _run_at_commit("doc hygiene", commit_only):
        check_doc_hygiene(report, docs)
    if _run_at_commit("route rosters", commit_only):
        check_route_rosters(report)
    if _run_at_commit("agent links", commit_only):
        check_agent_links(report)
    if _run_at_commit("test purposes", commit_only):
        check_test_purposes(report)
    if _run_at_commit("recorded deletions", commit_only):
        check_recorded_deletions(report)
    if _run_at_commit("spec seal", commit_only):
        check_spec_seal(report)
    if _run_at_commit("verdict file", commit_only):
        check_design_check_verdict(report)
    if _run_at_commit("check registry", commit_only):
        check_check_registry(report)
    if _run_at_commit("commit path", commit_only):
        check_commit_path(report)
    if _run_at_commit("no mechanism on screen", commit_only):
        check_no_mechanism_on_screen(report)
    if _run_at_commit("typed interpunct", commit_only):
        check_typed_interpunct(report)
    if _run_at_commit("suite lock", commit_only):
        check_suite_lock(report)
    if _run_at_commit("browser scope", commit_only):
        check_browser_scope(report)
    if _run_at_commit("spec map", commit_only):
        check_spec_map(report)
    if _run_at_commit("serve scope", commit_only):
        check_serve_scope(report)
    if _run_at_commit("guard scope", commit_only):
        check_guard_scope(report)
    if _run_at_commit("check numbering", commit_only) or _run_at_commit("numbering in code", commit_only):
        check_positional_references(report, docs)
    if _run_at_commit("audit invocation", commit_only):
        check_audit_invocation(report)
    if _run_at_commit("identifier spelling", commit_only):
        check_identifier_spelling(report)
    if _run_at_commit("shell substitution", commit_only):
        check_shell_substitution(report)
    if _run_at_commit("unscoped walk", commit_only):
        check_unscoped_walk(report)
    if _run_at_commit("import layering", commit_only):
        check_import_layering(report)
    if _run_at_commit("error words", commit_only):
        check_error_words(report)
    if _run_at_commit("identity writers", commit_only):
        check_identity_writers(report)
    if _run_at_commit("rule enforcement", commit_only):
        check_rule_enforcement(report)
    # Last, and it is the row that says the rows above are all of them. It reconciles this
    # file's check definitions against the calls in this function.
    #
    # IT DOES NOT ANSWER FOR ITSELF, and an earlier draft of this comment claimed it did.
    # Measured: delete this one line and every other row still prints green, the run exits
    # 0, and the `check dispatch` row is simply absent — the exact silent shrinkage the row
    # exists to catch, one level up. A detector cannot detect its own absence; that is the
    # shape of the thing, not a bug to patch, and no reconciliation added here can close it
    # because
    # the reconciler would need the same single call nothing vouches for. What catches it
    # is `--self-test`, whose last case calls check_dispatch() directly and asserts this
    # function names every check — and `--self-test` runs by hand, on no gate. So this line
    # is the root of the recursion: unwiring anything else fails the commit, and unwiring
    # THIS fails nothing automatic. docs/debts/ records it under the entry that shipped
    # the row; do not delete it on the strength of the audit staying green.
    #
    # TIER 2 (L12, 2026-09-28): `check_dispatch` reads THIS file's own source with `ast`,
    # not the tree it audits, so it costs the same in commit and CI mode and gates nothing
    # that a session edits — skipping it at commit only delays catching an unwired check
    # until CI, never lets one ship unnoticed to main.
    if _run_at_commit("check dispatch", commit_only):
        check_dispatch(report)
    if staged_only and _run_at_commit("coupling", commit_only):
        check_coupling(report)
    # AFTER EVERYTHING, because its subject is the other rows' subject counts — including
    # `coupling`, which only exists in staged mode. It is the one row that must see the
    # whole report, so it is the one row that cannot be anywhere but here.
    if _run_at_commit("subject counts", commit_only):
        check_subject_counts(report, staged_only)
    return report
