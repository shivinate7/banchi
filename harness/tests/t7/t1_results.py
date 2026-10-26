"""T7 group: a tune-only T1 run never replaces the committed holdout score.

`BANCHI_T1_SPLIT=tune` scores only the tune half, so the holdout group is empty and `holdout_accuracy`
is null. `t1_id_eval._write_results` used to write that payload over the committed
`harness/results/t1.json`, losing the holdout score the gate reads. A tune-only payload must leave the
committed file as it was (a refusal that raises is accepted too). A run that did score the holdout
still writes.

Every case copies the committed t1.json into a run folder and points `t1_id_eval.RESULTS_DIR` at it. The
real `harness/results/` is never written. The last case proves `run_folder`'s sweep: an old sibling run
folder goes, a new one stays, a folder that is not a run folder stays.

INTERFACE ASSUMED: `t1_id_eval._write_results(payload, config) -> (path, wrote)` and the module
global `t1_id_eval.RESULTS_DIR`, which it reads at call time.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from harness.tests import Checks
from harness.tests import t1_id_eval
from harness.tests.home import run_folder

COMMITTED = Path(t1_id_eval.RESULTS_DIR) / "t1.json"
DAY = 24 * 60 * 60


@contextmanager
def _results_dir_at(folder: Path):
    saved = t1_id_eval.RESULTS_DIR
    t1_id_eval.RESULTS_DIR = folder
    try:
        yield
    finally:
        t1_id_eval.RESULTS_DIR = saved


def _tune_only(committed: dict) -> dict:
    """The payload `t1_id_eval.main` builds for BANCHI_T1_SPLIT=tune: no holdout images, accuracy null."""
    payload = json.loads(json.dumps(committed))
    payload["split_requested"] = "tune"
    payload["splits"]["holdout"] = {"accuracy": None, "correct": 0, "images": 0}
    payload["holdout_accuracy"] = None
    payload["passed"] = False
    payload["overall_accuracy"] = payload["splits"]["tune"]["accuracy"]
    payload["holdout_misses"] = []
    payload["batch_ids"] = ["msgbatch_tune_only"]
    payload["generated_at"] = "2099-01-01T00:00:00+00:00"
    return payload


def check_tune_only_write_keeps_committed_holdout_score(checks: Checks) -> None:
    committed = json.loads(COMMITTED.read_text("utf-8"))
    if not checks.ok(committed.get("holdout_accuracy") is not None, "the committed t1.json carries a holdout score"):
        return
    with run_folder() as folder:
        copy = folder / "t1.json"
        shutil.copyfile(COMMITTED, copy)
        before = copy.read_bytes()
        # a refusal is an accepted fix; the file must still be unchanged
        with _results_dir_at(folder), contextlib.suppress(Exception, SystemExit):
            t1_id_eval._write_results(_tune_only(committed), "none")
        after = copy.read_bytes()
    checks.ok(
        after == before,
        "a tune-only write leaves the committed t1.json as it was",
        "holdout_accuracy {0!r} -> {1!r}".format(
            committed["holdout_accuracy"], json.loads(after.decode("utf-8")).get("holdout_accuracy")
        ),
    )


def check_a_run_that_scored_the_holdout_is_still_written(checks: Checks) -> None:
    committed = json.loads(COMMITTED.read_text("utf-8"))
    rerun = json.loads(json.dumps(committed))
    rerun["holdout_accuracy"] = 0.9853
    rerun["batch_ids"] = ["msgbatch_full_rerun"]
    with run_folder() as folder:
        copy = folder / "t1.json"
        shutil.copyfile(COMMITTED, copy)
        with _results_dir_at(folder):
            _, wrote = t1_id_eval._write_results(rerun, "none")
        stored = json.loads(copy.read_text("utf-8")).get("holdout_accuracy")
    checks.ok(wrote and stored == 0.9853, "a full run with a new holdout score is written", f"wrote={wrote} stored={stored!r}")


def check_run_folder_sweeps_old_siblings_and_keeps_new_ones(checks: Checks) -> None:
    with run_folder() as outer:
        root = outer / "sweep-root"
        root.mkdir()
        old, new = root / f"1-{uuid.uuid4()}", root / f"2-{uuid.uuid4()}"
        stray = root / "not-a-run-folder"
        for path in (old, new, stray):
            path.mkdir()
        now = time.time()
        for path, age in ((old, 2 * DAY), (stray, 2 * DAY), (new, 3600)):
            os.utime(path, (now - age, now - age))
        with run_folder(root) as mine:
            checks.ok(not old.exists(), "an old sibling run folder is removed")
            checks.ok(new.exists(), "a new sibling run folder is kept")
            checks.ok(stray.exists(), "a folder that is not a run folder is kept")
            checks.ok(mine.parent == root and mine.name.startswith(f"{os.getpid()}-"), "this run's folder is <pid>-<UUID> under the root")
        checks.ok(not mine.exists(), "teardown removes this run's folder")


CHECKS = (
    check_tune_only_write_keeps_committed_holdout_score,
    check_a_run_that_scored_the_holdout_is_still_written,
    check_run_folder_sweeps_old_siblings_and_keeps_new_ones,
)
