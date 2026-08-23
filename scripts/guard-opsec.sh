#!/usr/bin/env bash
# Blocks the two things a CLAUDE.md line cannot reliably stop.
#
# 1. Code-card photos and code strings escaping into the repo. A live unredeemed code is
#    a bearer instrument; anyone who reads the image or the printed string owns the code.
#    captures/ is gitignored, everywhere else is not.
# 2. Fixtures being edited. They are ground truth for the round-trip test; if they
#    drift, the test still passes and means nothing.
#
# Exit 2 blocks the tool call and returns stderr to Claude. Every other exit is 0: THE
# GUARD FAILS OPEN ON ITS OWN BUGS. A guard that blocks every write when python3 is
# missing or its own regex is wrong gets disabled inside a day — that is not a guess, it
# is this file's own history — and a disabled guard protects nothing. The commit-time
# twin (scripts/githooks/pre-commit) is the backstop for anything this lets through.
#
# HISTORY, because it decides the shape of the code rule below. This hook was disabled
# 2026-08-03: it blocked any write containing a code-shaped string, including placeholders
# in prose ABOUT the format, and cost two blocked writes in one session. D16 recorded the
# ruling — the fix is a narrower pattern, never a toggle — and D24 made "revisit before
# the codes track handles real cards" come due. Re-enabled 2026-08-23 with the narrowing
# below.
#
# THE NARROWED CODE RULE. The printed layout is four hyphen-separated uppercase
# alphanumeric groups of length three, four, three, three (described in words here, and
# assembled from parts below, so this file's own diff never matches the commit-time
# pattern). A candidate with that shape blocks only when ALL of these hold:
#
#   - it stands alone: not flanked by another letter, digit or hyphen, so a window inside
#     a longer hyphen chain or a token glued into an identifier never fires;
#   - it mixes letters AND digits, so a letters-only alphabet-walk prose example and a
#     phone-shaped digits-only run both pass;
#   - no group is one character repeated, so the all-X layout placeholder and its
#     `NNN-`/`AAA-` cousins pass.
#
# CONTEXT EXCLUSIONS WERE CONSIDERED AND REJECTED. Skipping .md files or comment lines
# (the note in .claude/settings.json suggested both) would open a hole exactly where a
# real code is likeliest to leak — listing copy, README prose, a doc pasting a run's
# output. The narrowing is by shape, everywhere.
#
# FALSE-POSITIVE BUDGET, designed to: zero blocked writes on every recorded and
# reconstructable placeholder shape (format prose, all-X and all-N placeholders,
# letters-only examples, digits-only runs, windows inside longer chains). The residual
# false positive is a placeholder deliberately crafted to look real — mixed letters and
# digits, no repeated group, standing alone — which the guard cannot tell from a live
# code and is SUPPOSED to block; the message names the placeholder convention that
# passes. FALSE-NEGATIVE BUDGET: roughly 2% of real codes (letters-only, or carrying an
# all-same group, under a uniform-alphabet estimate) pass this hook and are caught at
# commit time by the pre-commit's deliberately broad twin of this rule. The pair is the
# design: PreToolUse narrow so it is never muted, commit-time broad so nothing tracked
# ever carries a code.

set -uo pipefail

payload="$(cat)"
path="$(printf '%s' "$payload" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)" || path=""

[ -z "$path" ] && exit 0

case "$path" in
  */fixtures/*)
    echo "BLOCKED: fixtures/ is ground truth for the round-trip test and is read-only. If the schema genuinely changed, re-export from TCGplayer and commit that as a new fixture." >&2
    exit 2
    ;;
esac

case "$path" in
  */captures/*) exit 0 ;;
  *.png|*.jpg|*.jpeg|*.webp|*.heic)
    echo "BLOCKED: image write outside captures/. Code-card photos are bearer instruments and must never reach a tracked path. Write to captures/ or explain why this image is safe." >&2
    exit 2
    ;;
esac

# The code rule. The verdict is a masked echo of the first live-shaped match (first group
# kept, the rest starred out) — never the full string, so a real code is not repeated
# into stderr. Empty verdict means pass, and any failure inside python lands in the
# `|| verdict=""` arm: fail open, per the header.
verdict="$(printf '%s' "$payload" | python3 -c '
import json, re, sys
try:
    tool_input = json.load(sys.stdin).get("tool_input", {})
    text = tool_input.get("content", "") or tool_input.get("new_string", "")
    if isinstance(text, str) and text:
        g3 = "[A-Z0-9]{3}"
        g4 = "[A-Z0-9]{4}"
        body = "-".join((g3, g4, g3, g3))
        shape = re.compile("(?<![A-Za-z0-9-])" + body + "(?![A-Za-z0-9-])")
        for match in shape.finditer(text):
            candidate = match.group(0)
            groups = candidate.split("-")
            if any(len(set(group)) == 1 for group in groups):
                continue  # a group of one repeated character is a placeholder
            if not (re.search("[0-9]", candidate) and re.search("[A-Z]", candidate)):
                continue  # letters-only prose example, or a digits-only run
            print(groups[0] + "-****-***-***")
            break
except Exception:
    pass
' 2>/dev/null)" || verdict=""

if [ -n "$verdict" ]; then
  # The layout in the message is assembled at runtime so this file never carries it.
  p3="XXX"; p4="XXXX"
  echo "BLOCKED: content carries what looks like a live printed code (${verdict}). A live unredeemed code is a bearer instrument — never write one into a repo file. Use the ${p3}-${p4}-${p3}-${p3} placeholder layout, which this guard deliberately passes." >&2
  exit 2
fi

exit 0
