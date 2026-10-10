"""The one launchd install/remove helper for a daily job on the owner's Mac (main tree only).

Imported by `price-refresh-daily.py`. `demo-mirror-daily.py` still carries its own copy of this
logic: it sits under the D295 auto-merge fence and is left untouched on purpose. Migrate it to
this helper in its own PR, with the fence's selftest re-run.
"""
import os
import plistlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import machinedir  # noqa: E402


def agent(label, script, root, hour, minute, log, remove):
    plist = Path.home() / "Library" / "LaunchAgents" / (label + ".plist")
    uid = "gui/%d" % os.getuid()
    if remove:
        subprocess.run(["launchctl", "bootout", "%s/%s" % (uid, label)], capture_output=True)
        plist.unlink(missing_ok=True)
        machinedir.remove_old_agent(label)
        print("removed", label)
        return 0
    if (Path(root) / ".git").is_file():
        print("refusing: linked worktree. Install from the main checkout.")
        return 1
    venv = Path(root) / ".venv" / "bin" / "python"
    payload = {
        "Label": label,
        "ProgramArguments": [str(venv if venv.exists() else sys.executable), str(script)],
        "WorkingDirectory": str(root),
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(Path(log).with_suffix(".out")),
        "StandardErrorPath": str(Path(log).with_suffix(".out")),
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    }
    plist.parent.mkdir(parents=True, exist_ok=True)
    with open(plist, "wb") as f:
        plistlib.dump(payload, f)
    subprocess.run(["launchctl", "bootout", "%s/%s" % (uid, label)], capture_output=True)
    r = subprocess.run(["launchctl", "bootstrap", uid, str(plist)], capture_output=True, text=True)
    print("bootstrap failed: " + r.stderr.strip() if r.returncode else "installed %s, daily %02d:%02d" % (label, hour, minute))
    return r.returncode
