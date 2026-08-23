"""`identifications.json` — answers already paid for.

Keyed by POSITION, because position is the card's identity. The photo hash and the prompt
fingerprint ride along as staleness checks, not as part of the key, and each does a
different job:

  photo sha256        a re-shot card gets re-read. Without this the cache would confidently
                      return the answer to a picture that no longer exists — the single
                      worst failure available to a cache in this pipeline, because the
                      answer is plausible and the photo that disproves it is gone.
  prompt fingerprint  RECORDED, and deliberately NOT a reuse gate.

WHY A PROMPT CHANGE DOES NOT INVALIDATE. T1 must invalidate strictly — a score has to come
from the prompt being scored, and the harness already does that. Production inventory is a
different problem: re-reading thousands of correct answers because one line was reworded
costs real money to mostly reproduce them. So a stale-prompt answer is reused, and the run
report says how many came from an older prompt. The fingerprint's production value is that
it is recorded, which is what makes a *targeted* re-read possible later.

`--reidentify-stale` is that targeted re-read: only entries that are both WEAK (confidence
`low`, or currently sitting in a queue) and UNCLEARED. Everything else stands.

A HUMAN-CLEARED IDENTIFICATION IS PERMANENT. Once someone has looked at the photo and picked
the row, no re-run, prompt change, or re-identification pass overwrites it. If a later run
happens to read that photo and disagrees, `disagreements()` reports it — cheap evidence that
either the prompt improved or a clearing was a mistake — but the human answer stands.

NOTHING SETS `cleared_by_human` ON THE CACHE. The review screen shipped 2026-08-13 and its
answer route sets the flag on the queue entry, not here — deliberately: marking a model
answer human-cleared would claim a person vouched for the NAME AND NUMBER the model read,
while what he picked was a catalog row. `server/capture_server.py:do_review_answer` carries
the argument. Gate B's 16 answers on 2026-08-22 went that way, so the permanence rule above
is still real code on an untravelled path — and whether the chosen row should replace the
model's answer here is the open decision that run put on the table.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

WEAK_CONFIDENCE = "low"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class CacheEntry:
    """One paid-for answer, with everything needed to decide whether it still applies."""

    identification: dict
    photo_sha256: str
    prompt_fingerprint: str
    at: str
    cleared_by_human: bool = False

    @property
    def confidence(self) -> Optional[str]:
        return self.identification.get("confidence")

    @property
    def weak(self) -> bool:
        return self.confidence == WEAK_CONFIDENCE


@dataclass
class Cache:
    entries: Dict[str, CacheEntry]

    @classmethod
    def parse(cls, payload: Optional[dict]) -> "Cache":
        entries = {}
        for key, record in (payload or {}).items():
            if key.startswith("_"):
                continue
            known = {k: v for k, v in record.items() if k in CacheEntry.__annotations__}
            try:
                entries[key] = CacheEntry(**known)
            except TypeError:
                continue  # a record from an older shape; re-reading it is cheap
        return cls(entries=entries)

    def to_payload(self) -> dict:
        return {key: asdict(entry) for key, entry in sorted(self.entries.items())}

    def __len__(self) -> int:
        return len(self.entries)

    def get(self, key: str) -> Optional[CacheEntry]:
        return self.entries.get(key)

    def reusable(self, key: str, photo_sha256: str) -> Optional[CacheEntry]:
        """The answer to reuse for this position, or None to send the card again.

        A cleared answer is returned whatever the photo says — that is what permanent means.
        Otherwise the photo has to be the same photo.
        """
        entry = self.entries.get(key)
        if entry is None:
            return None
        if entry.cleared_by_human:
            return entry
        if entry.photo_sha256 != photo_sha256:
            return None
        return entry

    def stale_prompt(self, prompt_fingerprint: str) -> List[str]:
        """Positions whose answer came from an older prompt. Reported, not invalidated."""
        return sorted(
            key
            for key, entry in self.entries.items()
            if entry.prompt_fingerprint != prompt_fingerprint
        )

    def weak_and_uncleared(
        self, prompt_fingerprint: str, queued: Iterable[str] = ()
    ) -> List[str]:
        """What `--reidentify-stale` re-reads: weak, uncleared, and read by an older prompt.

        Weak means the model said `low`, OR the card is sitting in a queue right now — a
        card in a queue is one the pipeline already declined to trust, whatever the model's
        own confidence claimed.
        """
        in_queue = set(queued)
        out = []
        for key, entry in self.entries.items():
            if entry.cleared_by_human:
                continue
            if entry.prompt_fingerprint == prompt_fingerprint:
                continue
            if entry.weak or key in in_queue:
                out.append(key)
        return sorted(out)

    def put(
        self,
        key: str,
        identification: dict,
        photo_sha256: str,
        prompt_fingerprint: str,
    ) -> Optional[dict]:
        """Store an answer. Refuses to overwrite a cleared one; reports a disagreement.

        Returns the disagreement record when a cleared entry was left in place and the new
        answer differs, so the caller can put it in the run report.
        """
        existing = self.entries.get(key)
        if existing is not None and existing.cleared_by_human:
            if _differs(existing.identification, identification):
                return {
                    "position": key,
                    "human": _summary(existing.identification),
                    "model": _summary(identification),
                }
            return None
        self.entries[key] = CacheEntry(
            identification=identification,
            photo_sha256=photo_sha256,
            prompt_fingerprint=prompt_fingerprint,
            at=now(),
        )
        return None


def _summary(identification: dict) -> str:
    return "{0} {1}/{2}".format(
        identification.get("name"),
        identification.get("number"),
        identification.get("printed_total"),
    )


def _differs(left: dict, right: dict) -> bool:
    keys = ("name", "number", "printed_total")
    return any(str(left.get(k)) != str(right.get(k)) for k in keys)
