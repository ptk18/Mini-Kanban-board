#!/usr/bin/env bash
# Build the bounded, read-only evidence packet the responder reasons about.
#
#   oncall/collect-evidence.sh <alertname> <out.md> [<alert-payload.json>]
#
# Every query here is read-only and allowlisted (nothing is parameterised
# by the alert payload except the alert name in the heading). The packet
# never contains environment variables, credentials, request bodies,
# headers or e-mails: the telemetry it reads was built not to have them,
# and this script only reads telemetry and git metadata. Output is capped.
set -euo pipefail

ALERT="${1:?alertname}"
OUT="${2:?output file}"
PAYLOAD="${3:-}"
PROM="${PROM:-http://localhost:9090}"
LOKI="${LOKI:-http://localhost:3100}"
TEMPO="${TEMPO:-http://localhost:3200}"
MAX_BYTES="${MAX_BYTES:-40000}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

q() { curl -fsS -G "$PROM/api/v1/query" --data-urlencode "query=$1" 2>/dev/null \
      | python3 -c 'import json,sys
d=json.load(sys.stdin)
for r in d["data"]["result"][:12]:
    m={k:v for k,v in r["metric"].items() if k in ("http_route","http_request_method","http_response_status_code","http_status_class","alertname","alertstate")}
    print("  ", m, "=>", r["value"][1])
if not d["data"]["result"]: print("   (no data)")' || echo "   (query failed)"; }

{
  echo "# Evidence packet: $ALERT"
  echo "collected: $(date -u +%Y-%m-%dT%H:%M:%SZ) by oncall/collect-evidence.sh (read-only, allowlisted)"
  echo
  if [ -n "$PAYLOAD" ] && [ -f "$PAYLOAD" ]; then
    echo "## Alert (from Alertmanager)"
    python3 -c 'import json,sys
d=json.load(open(sys.argv[1]))
for a in d.get("alerts", []):
    print("-", a["labels"].get("alertname"), a.get("status"), "| since", a.get("startsAt"))
    for k in ("summary","description","runbook"):
        if a.get("annotations",{}).get(k): print("  ", k+":", a["annotations"][k])' "$PAYLOAD"
    echo
  fi

  echo "## Prometheus (now)"
  echo "- alerts:"; q 'ALERTS{alertstate="firing"}'
  echo "- 5xx ratio on /boards*|/cards* over 1m:"; q 'sum(rate(kanban_http_requests_total{http_route=~"/boards.*|/cards.*", http_response_status_code=~"5.."}[1m])) / sum(rate(kanban_http_requests_total{http_route=~"/boards.*|/cards.*"}[1m]))'
  echo "- request rate by route and status (1m):"; q 'sum by (http_request_method, http_route, http_response_status_code) (rate(kanban_http_requests_total[1m])) > 0'
  echo "- p95 latency ms (5m):"; q 'histogram_quantile(0.95, sum by (le) (rate(kanban_http_request_duration_milliseconds_bucket[5m])))'
  echo "- /health probe status:"; q 'httpcheck_status{http_status_class="2xx"}'
  echo "- seconds since last successful /health probe:"; q 'time() - max(timestamp(httpcheck_status{http_status_class="2xx", http_status_code="200"}))'
  echo "- card moves in the last 5m:"; q 'sum(increase(kanban_card_moves_total[5m]))'
  echo

  echo "## Loki: last error log lines (level=error, newest first, max 25)"
  curl -fsS -G "$LOKI/loki/api/v1/query_range" --data-urlencode 'query={service_name="mini-kanban-api"} | detected_level="error"' --data-urlencode 'limit=25' --data-urlencode "start=$(( $(date +%s) - 1800 ))000000000" 2>/dev/null \
    | python3 -c 'import json,sys
d=json.load(sys.stdin); n=0
for s in d["data"]["result"]:
    for ts,line in s["values"]:
        print("  ", line[:400]); n+=1
if n==0: print("   (none in the last 30 minutes)")' || echo "   (query failed)"
  echo

  echo "## Tempo: one failing trace (first error log line's trace_id)"
  TID=$(curl -fsS -G "$LOKI/loki/api/v1/query_range" --data-urlencode 'query={service_name="mini-kanban-api"} | detected_level="error"' --data-urlencode 'limit=1' --data-urlencode "start=$(( $(date +%s) - 1800 ))000000000" 2>/dev/null \
    | python3 -c 'import json,sys,re
d=json.load(sys.stdin)
for s in d["data"]["result"]:
    for ts,line in s["values"]:
        m=re.search(r"\"trace_id\": \"([0-9a-f]+)\"", line)
        if m: print(m.group(1)); raise SystemExit' 2>/dev/null || true)
  if [ -n "${TID:-}" ]; then
    echo "trace_id: $TID"
    curl -fsS "$TEMPO/api/traces/$TID" 2>/dev/null | python3 -c 'import json,sys
d=json.load(sys.stdin)
for b in d.get("batches",[]):
    for ss in b.get("scopeSpans",[]):
        for s in ss.get("spans",[]):
            dur=(int(s["endTimeUnixNano"])-int(s["startTimeUnixNano"]))/1e6
            attrs={a["key"]:list(a["value"].values())[0] for a in s.get("attributes",[]) if a["key"] in ("http.route","http.response.status_code","db.statement","exception.type","exception.message")}
            st=s.get("status",{}).get("code","")
            print(f"   {s["name"]:<40} {dur:7.1f} ms status={st} {attrs}")' || echo "   (trace not found)"
  else
    echo "   (no error log line with a trace_id)"
  fi
  echo

  echo "## Containers"
  (cd "$ROOT" && docker compose ps --format '  {{.Service}} {{.Status}}' 2>/dev/null) || echo "   (docker compose ps failed)"
  echo

  echo "## Repository"
  echo "- HEAD: $(cd "$ROOT" && git log -1 --format='%h %s (%cr)')"
  echo "- recent commits:"; (cd "$ROOT" && git log --oneline -8 | sed 's/^/   /')
  echo "- uncommitted changes:"; (cd "$ROOT" && git status --short | sed 's/^/   /' | head -20)
  echo "- where card moves fail on purpose, if the fault switch is on: backend/app/fault.py, backend/app/routers/debug.py, check_card_move() in backend/app/routers/cards.py"
} | head -c "$MAX_BYTES" > "$OUT"

echo "evidence packet: $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes)"
