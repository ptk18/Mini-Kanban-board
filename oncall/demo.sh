#!/usr/bin/env bash
# The whole loop, end to end, on the local stack:
#   webhook receiver up -> fault injected -> alert fires -> Alertmanager calls
#   the receiver -> responder collects evidence, reasons in a worktree,
#   proposes clear_demo_fault -> responder clears it -> recovery verified.
# Prints the report. Needs `make observe` and `make seed` to have run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p oncall/reports
BEFORE=$(ls oncall/reports/*.md 2>/dev/null | grep -v '\.evidence\.md$' | wc -l | tr -d ' ')

# Fresh Alertmanager: its notification log may still hold a "firing" entry
# from an earlier demo whose "resolved" never reached a receiver, and that
# would deduplicate the new firing away.
docker compose -f docker-compose.yml -f observability/compose.yaml up -d --no-deps --force-recreate --wait alertmanager >/dev/null 2>&1
echo "alertmanager recreated (fresh notification log)"

python3 oncall/server.py > oncall/reports/server.log 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null; echo "receiver stopped"' EXIT
sleep 1
curl -fsS http://localhost:9000/health >/dev/null && echo "receiver up on :9000 (pid $SERVER)"

observability/demo-alert.sh --keep

echo "waiting for the responder (Alertmanager group_wait 10s + diagnosis; up to 12 min)..."
deadline=$(( $(date +%s) + 720 ))
while :; do
  NOW=$(ls oncall/reports/*.md 2>/dev/null | grep -v '\.evidence\.md$' | wc -l | tr -d ' ')
  if [ "$NOW" -gt "$BEFORE" ]; then
    REPORT=$(ls -t oncall/reports/*.md | grep -v '\.evidence\.md$' | head -1)
    echo; echo "================ $REPORT ================"
    sed -n '1,/^## Run log/p' "$REPORT"
    echo "(evidence and run log are in the file)"
    break
  fi
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "no report within 12 minutes; receiver log:"; tail -20 oncall/reports/server.log; exit 1
  fi
  sleep 10
done
echo; echo "receiver log:"; cat oncall/reports/server.log
