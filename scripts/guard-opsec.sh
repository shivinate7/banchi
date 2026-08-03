#!/usr/bin/env bash
# Blocks the two things a CLAUDE.md line cannot reliably stop.
#
# 1. Code-card photos escaping into the repo. A live unredeemed code is a bearer
#    instrument; anyone who reads the image owns the code. captures/ is gitignored,
#    everywhere else is not.
# 2. Fixtures being edited. They are ground truth for the round-trip test; if they
#    drift, the test still passes and means nothing.
#
# Exit 2 blocks the tool call and returns stderr to Claude.

set -uo pipefail

payload="$(cat)"
path="$(printf '%s' "$payload" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)"

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

# Printed code format XXX-XXXX-XXX-XXX in any content being written.
content="$(printf '%s' "$payload" | python3 -c 'import sys,json;d=json.load(sys.stdin).get("tool_input",{});print(d.get("content","") or d.get("new_string",""))' 2>/dev/null)"
if printf '%s' "$content" | grep -Eq '[A-Z0-9]{3}-[A-Z0-9]{4}-[A-Z0-9]{3}-[A-Z0-9]{3}'; then
  echo "BLOCKED: content matches the printed code-card format (XXX-XXXX-XXX-XXX). Never commit a live code. Use a placeholder." >&2
  exit 2
fi

exit 0
