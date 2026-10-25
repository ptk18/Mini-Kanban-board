#!/usr/bin/env bash
# Post-deploy smoke test.
#
#   scripts/smoke.sh <api-base-url> [<frontend-base-url>] [<expected-commit-sha>]
#
# Polls the API's /health until it answers {"status":"ok"} — and, when a sha is
# given, until the reported "version" starts with that sha, which proves the
# NEW build is the one serving (not the previous deploy still winding down).
# Then checks the frontend's /login renders. Free-tier hosts wake from sleep
# in about a minute, so the default budget is generous.
#
#   SMOKE_TIMEOUT   seconds to keep trying (default 600)
#   SMOKE_INTERVAL  seconds between attempts (default 10)
set -euo pipefail

api="${1:?usage: smoke.sh <api-base-url> [<frontend-base-url>] [<expected-sha>]}"
web="${2:-}"
want="${3:-}"
timeout="${SMOKE_TIMEOUT:-600}"
interval="${SMOKE_INTERVAL:-10}"
api="${api%/}"; web="${web%/}"

deadline=$(( $(date +%s) + timeout ))
attempt=0
while :; do
  attempt=$(( attempt + 1 ))
  body=$(curl -fsS --max-time 15 "$api/health" 2>/dev/null || true)
  status=$(printf '%s' "$body" | sed -n 's/.*"status":"\([^"]*\)".*/\1/p')
  version=$(printf '%s' "$body" | sed -n 's/.*"version":"\([^"]*\)".*/\1/p')
  # Version matches when none was asked for, or either value is a prefix of
  # the other (short vs. full sha).
  if [[ "$status" == "ok" && ( -z "$want" || "$version" == "$want"* || ( -n "$version" && "$want" == "$version"* ) ) ]]; then
    echo "api ok: $api/health -> $body (attempt $attempt)"
    break
  fi
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "SMOKE FAILED: $api/health after ${timeout}s; last body: '${body:-<none>}' (wanted version ${want:-any})" >&2
    exit 1
  fi
  echo "waiting for $api/health (got status='${status:-}' version='${version:-}', want '${want:-any}')..."
  sleep "$interval"
done

if [ -n "$web" ]; then
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$web/login" || true)
  if [ "$code" != "200" ]; then
    echo "SMOKE FAILED: $web/login -> HTTP ${code:-none}" >&2
    exit 1
  fi
  echo "web ok: $web/login -> 200"
fi
echo "SMOKE PASSED"
