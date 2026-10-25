#!/usr/bin/env bash
# Trigger the KanbanApiErrors alert on purpose and watch it fire.
#
#   observability/demo-alert.sh            # inject, drive traffic, wait for FIRING, clear the fault
#   observability/demo-alert.sh --keep     # same, but leave the fault on (for the on-call demo, #46)
#
# Needs the stack from `make observe` (the overlay sets FAULT_INJECTION=1 on
# the backend, which is what registers POST /debug/fault). Nothing here is
# available in production.
set -euo pipefail

API="${API:-http://localhost:8000}"
PROM="${PROM:-http://localhost:9090}"
ALERTMANAGER="${ALERTMANAGER:-http://localhost:9093}"
KEEP=0; [ "${1:-}" = "--keep" ] && KEEP=1

say() { printf '\033[1m%s\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }

cleanup() {
  if [ "$KEEP" = 0 ]; then
    curl -fsS -X POST "$API/debug/fault" -H 'Content-Type: application/json' -d '{"card_move_fails": false}' >/dev/null && say "fault cleared"
  else
    say "fault LEFT ON (--keep); clear it with: curl -X POST $API/debug/fault -H 'Content-Type: application/json' -d '{\"card_move_fails\": false}'"
  fi
}
trap cleanup EXIT

curl -fsS "$API/debug/fault" >/dev/null 2>&1 || { echo "POST /debug/fault is not available — start the stack with 'make observe' (sets FAULT_INJECTION=1)" >&2; exit 1; }

say "logging in as the seeded owner (run 'make seed' first if this fails)"
TOKEN=$(curl -fsS "$API/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"ada@example.com","password":"insurance-demo"}' | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
AUTH="Authorization: Bearer $TOKEN"
BOARD=$(curl -fsS "$API/boards" -H "$AUTH" | sed -n 's/.*"id":\([0-9]*\).*/\1/p' | head -1)
COLS=$(curl -fsS "$API/boards/$BOARD" -H "$AUTH" | python3 -c 'import json,sys; print(" ".join(str(c["id"]) for c in json.load(sys.stdin)["columns"]))')
CARDS=$(curl -fsS "$API/boards/$BOARD/cards" -H "$AUTH" | python3 -c 'import json,sys; print(" ".join(str(c["id"]) for c in json.load(sys.stdin)[:3]))')
set -- $COLS; FIRST=$1; LAST=${!#}

say "switching the fault on: card moves will answer 500"
curl -fsS -X POST "$API/debug/fault" -H 'Content-Type: application/json' -d '{"card_move_fails": true}'; echo

say "driving traffic: a card move every second (each one fails), plus healthy reads"
deadline=$(( $(date +%s) + 240 ))
n=0
while [ "$(date +%s)" -lt "$deadline" ]; do
  for c in $CARDS; do
    # Two moves per card so at least one changes its column (a move to the
    # column a card is already in is a no-op and succeeds).
    code=$(curl -s -o /dev/null -w '%{http_code}' -X PATCH "$API/cards/$c" -H "$AUTH" -H 'Content-Type: application/json' -d "{\"column_id\": $LAST}")
    code2=$(curl -s -o /dev/null -w '%{http_code}' -X PATCH "$API/cards/$c" -H "$AUTH" -H 'Content-Type: application/json' -d "{\"column_id\": $FIRST}")
    printf '%s/%s ' "$code" "$code2"
  done
  curl -s -o /dev/null "$API/boards/$BOARD/dashboard" -H "$AUTH"
  n=$((n + 1))
  state=$(curl -fsS "$PROM/api/v1/alerts" | python3 -c 'import json,sys; a=[x for x in json.load(sys.stdin)["data"]["alerts"] if x["labels"]["alertname"]=="KanbanApiErrors"]; print(a[0]["state"] if a else "inactive")')
  printf '| KanbanApiErrors: %s\n' "$state"
  if [ "$state" = "firing" ]; then
    say "ALERT FIRING after $n rounds"
    curl -fsS "$PROM/api/v1/alerts" | python3 -c 'import json,sys; [print("  ", x["labels"]["alertname"], x["state"], "|", x["annotations"]["summary"]) for x in json.load(sys.stdin)["data"]["alerts"]]'
    sleep 15
    say "Alertmanager received:"
    curl -fsS "$ALERTMANAGER/api/v2/alerts" | python3 -c 'import json,sys; [print("  ", a["labels"]["alertname"], a["status"]["state"], "receivers:", [r["name"] for r in a["receivers"]]) for a in json.load(sys.stdin)]' || true
    exit 0
  fi
  sleep 1
done
echo "alert did not fire within 4 minutes" >&2
exit 1
