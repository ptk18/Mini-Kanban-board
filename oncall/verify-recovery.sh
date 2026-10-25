#!/usr/bin/env bash
# Is the incident over? Re-queries the alert condition and runs the smoke
# test. Exit 0 = RECOVERED, 1 = NOT RECOVERED. Used by responder.sh after an
# automatic action, and by hand.
#
#   oncall/verify-recovery.sh <alertname> [<seconds-to-wait>]
set -euo pipefail

ALERT="${1:?alertname}"
WAIT="${2:-150}"
PROM="${PROM:-http://localhost:9090}"
API="${API:-http://localhost:8000}"
WEB="${WEB:-http://localhost:3000}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# The failing journey itself, not just the metric: move one card to another
# column and back, as the seeded demo user. Skipped (with a note) when that
# account does not exist, e.g. on an unseeded database.
journey() {
  local token board cols cards first last code1 code2
  token=$(curl -fsS "$API/auth/login" -H 'Content-Type: application/json' -d '{"email":"ada@example.com","password":"insurance-demo"}' 2>/dev/null | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
  [ -n "$token" ] || { echo "skipped (no seed account)"; return 0; }
  board=$(curl -fsS "$API/boards" -H "Authorization: Bearer $token" | python3 -c 'import json,sys; b=json.load(sys.stdin); print(b[0]["id"] if b else "")')
  [ -n "$board" ] || { echo "skipped (no board)"; return 0; }
  cols=$(curl -fsS "$API/boards/$board" -H "Authorization: Bearer $token" | python3 -c 'import json,sys; print(" ".join(str(c["id"]) for c in json.load(sys.stdin)["columns"]))')
  cards=$(curl -fsS "$API/boards/$board/cards" -H "Authorization: Bearer $token" | python3 -c 'import json,sys; c=json.load(sys.stdin); print(c[0]["id"] if c else "", c[0]["column_id"] if c else "")')
  set -- $cols; first=$1; last=${!#}
  local card=${cards%% *} home=${cards##* } target
  [ -n "$card" ] || { echo "skipped (no card)"; return 0; }
  target=$last; [ "$home" = "$last" ] && target=$first
  code1=$(curl -s -o /dev/null -w '%{http_code}' -X PATCH "$API/cards/$card" -H "Authorization: Bearer $token" -H 'Content-Type: application/json' -d "{\"column_id\": $target}")
  code2=$(curl -s -o /dev/null -w '%{http_code}' -X PATCH "$API/cards/$card" -H "Authorization: Bearer $token" -H 'Content-Type: application/json' -d "{\"column_id\": $home}")
  echo "card $card moved $home -> $target -> $home: $code1 $code2"
  [ "$code1" = 200 ] && [ "$code2" = 200 ]
}

deadline=$(( $(date +%s) + WAIT ))
while :; do
  state=$(curl -fsS "$PROM/api/v1/alerts" 2>/dev/null | python3 -c "import json,sys; a=[x for x in json.load(sys.stdin)['data']['alerts'] if x['labels']['alertname']=='$ALERT']; print(a[0]['state'] if a else 'inactive')" || echo "unknown")
  case "$ALERT" in
    KanbanApiErrors)
      ratio=$(curl -fsS -G "$PROM/api/v1/query" --data-urlencode 'query=sum(rate(kanban_http_requests_total{http_route=~"/boards.*|/cards.*", http_response_status_code=~"5.."}[1m])) / sum(rate(kanban_http_requests_total{http_route=~"/boards.*|/cards.*"}[1m]))' | python3 -c "import json,sys; r=json.load(sys.stdin)['data']['result']; print(float(r[0]['value'][1]) if r and r[0]['value'][1] != 'NaN' else 0.0)")
      ok=$(python3 -c "print('yes' if $ratio < 0.05 else 'no')");;
    KanbanApiDown)
      age=$(curl -fsS -G "$PROM/api/v1/query" --data-urlencode 'query=time() - max(timestamp(httpcheck_status{http_status_class="2xx", http_status_code="200"}))' | python3 -c "import json,sys; r=json.load(sys.stdin)['data']['result']; print(float(r[0]['value'][1]) if r else 9999)")
      ok=$(python3 -c "print('yes' if $age < 30 else 'no')");;
    *) ok="unknown";;
  esac
  echo "$(date +%H:%M:%S) $ALERT state=$state condition_cleared=$ok"
  if [ "$state" = "inactive" ] && [ "$ok" = "yes" ]; then
    if ! "$ROOT/scripts/smoke.sh" "$API" "$WEB" >/dev/null 2>&1; then
      echo "alert cleared but the smoke test failed; retrying"
    elif [ "$ALERT" = KanbanApiErrors ] && ! out=$(journey); then
      echo "alert cleared but the card-move journey still fails ($out); retrying"
    else
      echo "RECOVERED: alert inactive, condition cleared, smoke test passed${out:+, journey: $out}"
      exit 0
    fi
  fi
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "NOT RECOVERED after ${WAIT}s (state=$state, condition_cleared=$ok)"
    exit 1
  fi
  sleep 10
done
