"""The one home of the per-user machine state: `~/.banchi` and the launchd labels.

Holds the port-slot registry, the suite lock and the daily jobs' logs. Every reader asks
`machine_dir()`, never `Path.home() / ".banchi"`. The first ask also moves a `~/.pkmnscan`
left by the old name, once: only when the new directory is missing. A failed move leaves the
old directory alone and the caller creates the new one.

A launchd agent installed under the old name is `remove_old_agent`'s to take out. Each agent's
`--remove` calls it, so one press leaves nothing under the old name.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def machine_dir() -> Path:
    home = Path.home()
    new, old = home / ".banchi", home / ".pkmnscan"
    if not new.exists() and old.is_dir():
        try:
            old.rename(new)
        except OSError:
            pass
    return new


def remove_old_agent(label: str) -> None:
    """Unload and delete the `com.pkmnscan.*` agent that `label` (a `com.banchi.*`) replaced."""
    old = label.replace("com.banchi.", "com.pkmnscan.", 1)
    if old == label:
        return
    subprocess.run(["launchctl", "bootout", "gui/%d/%s" % (os.getuid(), old)], capture_output=True)
    (Path.home() / "Library" / "LaunchAgents" / (old + ".plist")).unlink(missing_ok=True)
