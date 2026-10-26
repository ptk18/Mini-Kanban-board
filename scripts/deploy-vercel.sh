#!/usr/bin/env bash
# Deploy the API and the frontend to Vercel (free Hobby plan), as two
# projects built from the same repository:
#
#   mini-kanban-api[-dev]  backend/  FastAPI on the Python runtime (3.14)
#   mini-kanban-web[-dev]  frontend/ Next.js
#
#   scripts/deploy-vercel.sh prod     # https://mini-kanban-api.vercel.app, https://mini-kanban-web.vercel.app
#   scripts/deploy-vercel.sh dev      # the same with a -dev suffix
#
# Reads from the environment (or a git-ignored .env at the repo root):
#   VERCEL_TOKEN            required  https://vercel.com/account/tokens
#   DEPLOY_DATABASE_URL     required for prod: Postgres URL (Neon, Render external URL, …)
#   DEPLOY_DATABASE_URL_DEV required for dev (falls back to DEPLOY_DATABASE_URL)
#   OPENAI_API_KEY          optional: enables the AI card actions
#   VERCEL_SCOPE            optional: team slug, if not deploying to the personal account
#
# Order matters: the API is deployed first (the frontend bakes its URL in at
# build time), then the frontend, then the API again with CORS_ORIGINS set
# to the frontend's URL. Finally scripts/smoke.sh checks both. Secrets are
# passed to the CLI on stdin, never on the command line or in output.
set -euo pipefail

ENVIRONMENT="${1:-prod}"
case "$ENVIRONMENT" in prod) SUFFIX="" ;; dev) SUFFIX="-dev" ;; *) echo "usage: $0 prod|dev" >&2; exit 2 ;; esac

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# .env values may hold characters the shell treats specially (Neon URLs
# contain `&`), so parse it instead of sourcing it; the environment wins.
if [ -f .env ]; then
  while IFS= read -r line; do export "$line"; done < <(python3 - <<'PY'
import os, re
for raw in open(".env"):
    m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", raw)
    if not m or m.group(1) in os.environ:
        continue
    v = m.group(2)
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        v = v[1:-1]
    print(f"{m.group(1)}={v}")
PY
  )
fi

: "${VERCEL_TOKEN:?set VERCEL_TOKEN (https://vercel.com/account/tokens) in .env or the environment}"
if [ "$ENVIRONMENT" = dev ]; then DB_URL="${DEPLOY_DATABASE_URL_DEV:-${DEPLOY_DATABASE_URL:-}}"; else DB_URL="${DEPLOY_DATABASE_URL:-}"; fi
[ -n "$DB_URL" ] || { echo "set DEPLOY_DATABASE_URL${SUFFIX:+_DEV} (a Postgres URL reachable from the internet)" >&2; exit 2; }

API_PROJECT="mini-kanban-api$SUFFIX"
WEB_PROJECT="mini-kanban-web$SUFFIX"
VERSION="$(git rev-parse --short HEAD)"
V=(npx --yes vercel@65.2.0 --token "$VERCEL_TOKEN" --non-interactive)
[ -n "${VERCEL_SCOPE:-}" ] && V+=(--scope "$VERCEL_SCOPE")

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }

ensure_project() { # <name> <dir>
  "${V[@]}" project add "$1" >/dev/null 2>&1 || true   # fails harmlessly when it exists
  "${V[@]}" link --yes --project "$1" --cwd "$2" >/dev/null
}

set_env() { # <dir> <NAME> <value> secret|config
  # Secrets are write-only in Vercel; plain settings are stored as config so
  # this script can read them back (CORS_ORIGINS below).
  printf '%s' "$3" | "${V[@]}" env add "$2" --environment production --force --type "$4" --cwd "$1" >/dev/null 2>&1
}

has_env() { # <dir> <NAME>
  "${V[@]}" env ls production --cwd "$1" 2>/dev/null | grep -qE "^\s*$2\s"
}

deploy() { # <dir> [extra args...] -> prints the stable production URL
  local dir="$1"; shift
  local out err
  out=$(mktemp); err=$(mktemp)
  if ! "${V[@]}" deploy --prod --yes --cwd "$dir" "$@" >"$out" 2>"$err"; then
    echo "deploy of $dir failed:" >&2; grep -v '^[[:space:]]*$' "$err" | tail -15 >&2; rm -f "$out" "$err"; return 1
  fi
  # Non-interactive deploys print JSON on stdout. The per-deployment URL is
  # behind Vercel Authentication; productionUrl is the project's public alias.
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1]))["deployment"]; assert d["readyState"]=="READY", d["readyState"]; print(d["productionUrl"])' "$out"
  rm -f "$out" "$err"
}

say "projects: $API_PROJECT, $WEB_PROJECT ($ENVIRONMENT, version $VERSION)"
ensure_project "$API_PROJECT" backend
ensure_project "$WEB_PROJECT" frontend

say "API environment"
set_env backend DATABASE_URL "$DB_URL" secret
if ! has_env backend JWT_SECRET; then
  # Generated once and kept: rotating it would log every user out.
  set_env backend JWT_SECRET "$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" secret
fi
if [ -n "${OPENAI_API_KEY:-}" ]; then set_env backend OPENAI_API_KEY "$OPENAI_API_KEY" secret; fi
set_env backend OPENAI_MODEL "${OPENAI_MODEL:-gpt-4.1-mini}" config
cors_now() { "${V[@]}" env pull --environment production --cwd backend /dev/stdout 2>/dev/null | sed -n 's/^CORS_ORIGINS="\{0,1\}\([^"]*\)"\{0,1\}$/\1/p'; }
[ -n "$(cors_now)" ] || set_env backend CORS_ORIGINS "https://$WEB_PROJECT.vercel.app" config

say "deploying the API"
API_URL=$(deploy backend --env "APP_VERSION=$VERSION")
echo "API: $API_URL"

say "deploying the frontend (NEXT_PUBLIC_API_URL=$API_URL)"
set_env frontend NEXT_PUBLIC_API_URL "$API_URL" config
WEB_URL=$(deploy frontend --build-env "NEXT_PUBLIC_API_URL=$API_URL")
echo "Web: $WEB_URL"

if [ "$(cors_now)" != "$WEB_URL" ]; then
  say "pointing the API's CORS_ORIGINS at $WEB_URL and redeploying it"
  set_env backend CORS_ORIGINS "$WEB_URL" config
  API_URL=$(deploy backend --env "APP_VERSION=$VERSION")
fi

say "smoke test"
SMOKE_TIMEOUT=180 "$ROOT/scripts/smoke.sh" "$API_URL" "$WEB_URL" "$VERSION"
echo
echo "API_URL=$API_URL"
echo "WEB_URL=$WEB_URL"
