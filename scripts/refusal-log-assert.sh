# Sourced by each guard's self-test: the refusal log's well-formedness check, written once.
# `refusal_line_ok <log> <rule> [<session>]`: the log holds exactly ONE line, with five
# TAB-separated fields — ISO time, `<rule>`, a snippet of at most 80 characters, `<session>`
# (when given), and a checkout — and returns 0 when it does, 1 with the reason on stdout when
# it does not. The line format's home is scripts/refusal_log.py.
refusal_line_ok() {
  local log="$1" rule="$2" session="${3-}"
  [ -f "$log" ] || { echo "no log written"; return 1; }
  [ "$(wc -l < "$log" | tr -d ' ')" = "1" ] || { echo "not exactly one line: $(wc -l < "$log")"; return 1; }
  awk -F'\t' -v rule="$rule" -v session="$session" '
    NF != 5 { print "fields: " NF; exit 1 }
    $1 !~ /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]{8}[+-][0-9]{4}$/ { print "bad time: " $1; exit 1 }
    $2 != rule { print "rule: " $2; exit 1 }
    length($3) > 80 { print "snippet too long"; exit 1 }
    session != "" && $4 != session { print "session: " $4; exit 1 }
    $5 == "" { print "no checkout"; exit 1 }' "$log"
}
