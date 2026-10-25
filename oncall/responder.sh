#!/usr/bin/env bash
# The on-call responder: evidence -> isolated worktree -> headless Claude
# Code -> policy check -> (bounded) action -> recovery verification -> report.
#
#   oncall/responder.sh <alertname> [<alert-payload.json>]
#
# Everything the model may do is decided here and in autonomy-policy.yaml,
# not by the model: it runs with a fixed tool allowlist, in a worktree, with
# a scrubbed environment (no JWT_SECRET, DATABASE_URL, OPENAI_API_KEY, GEMINI_API_KEY,
# RENDER_*), a turn cap and a dollar cap. Its answer must match
# response.schema.json; anything else is treated as "escalate".
set -euo pipefail

ALERT="${1:?alertname}"
PAYLOAD="${2:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HERE="$ROOT/oncall"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN="$TS-$ALERT"
REPORTS="$HERE/reports"; mkdir -p "$REPORTS"
REPORT="$REPORTS/$RUN.md"
EVIDENCE="$REPORTS/$RUN.evidence.md"
ANSWER="$REPORTS/$RUN.answer.json"
WORKTREES="$HERE/worktrees"; mkdir -p "$WORKTREES"
WT="$WORKTREES/$RUN"
BRANCH="oncall/$RUN"
API="${API:-http://localhost:8000}"

policy() { python3 "$HERE/policy.py" "$1"; }
MAX_TURNS="$(policy responder.max_turns)"; MAX_BUDGET="$(policy responder.max_budget_usd)"
MAX_TURNS="${MAX_TURNS:-30}"; MAX_BUDGET="${MAX_BUDGET:-3}"

say() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*" | tee -a "$REPORT.log"; }
escalate() { # <reason>
  {
    echo "# NEEDS HUMAN — $ALERT ($TS)"
    echo
    echo "**Reason:** $1"
    echo
    [ -f "$ANSWER" ] && { echo '## Responder answer'; echo '```json'; cat "$ANSWER"; echo; echo '```'; echo; }
    echo "## Evidence"; echo; cat "$EVIDENCE" 2>/dev/null || echo "(none)"
  } > "$REPORT"
  say "ESCALATED: $1 -> $REPORT"
  exit 2
}

say "responder start: $ALERT (turns<=$MAX_TURNS, budget<=\$$MAX_BUDGET)"

# 1. Evidence (read-only, allowlisted).
"$HERE/collect-evidence.sh" "$ALERT" "$EVIDENCE" "$PAYLOAD" | tee -a "$REPORT.log"

# 2. Isolated worktree on a fresh branch from the current HEAD.
git -C "$ROOT" worktree add -q -b "$BRANCH" "$WT" HEAD
say "worktree: $WT ($BRANCH)"
( cd "$WT/backend" && uv sync --frozen -q 2>/dev/null ) || say "warning: uv sync in the worktree failed (tests may not run)"

# 3. Headless Claude Code, strictly bounded.
PROMPT="$(cat "$HERE/prompt.md"; echo; cat "$EVIDENCE")"
set +e
(
  cd "$WT" && env -u CLAUDECODE -u JWT_SECRET -u DATABASE_URL -u OPENAI_API_KEY -u GEMINI_API_KEY -u RENDER_DEPLOY_HOOK_API_DEV -u RENDER_DEPLOY_HOOK_WEB_DEV -u RENDER_DEPLOY_HOOK_API_PROD -u RENDER_DEPLOY_HOOK_WEB_PROD \
    claude -p "$PROMPT" \
      --safe-mode --no-session-persistence \
      --output-format json --json-schema "$(cat "$HERE/response.schema.json")" \
      --max-turns "$MAX_TURNS" --max-budget-usd "$MAX_BUDGET" \
      --permission-mode dontAsk \
      --allowedTools "StructuredOutput" "Read" "Grep" "Glob" "Edit" "Write" "Bash(uv run pytest:*)" "Bash(git diff:*)" "Bash(git status:*)" "Bash(git log:*)" "Bash(git show:*)" \
      --disallowedTools "WebFetch" "WebSearch" "Task" "Agent" "Workflow" "EnterWorktree" "ExitWorktree" "Skill" "NotebookEdit" "TaskOutput" "RemoteTrigger" "PushNotification" "CronCreate" "ScheduleWakeup" "Monitor" \
      --add-dir "$WT" < /dev/null
) > "$ANSWER.raw" 2> "$REPORT.claude.err"
CLAUDE_EXIT=$?
set -e
say "claude exit $CLAUDE_EXIT"
if [ "$CLAUDE_EXIT" != 0 ] || [ ! -s "$ANSWER.raw" ]; then
  escalate "the responder produced no answer (claude exit $CLAUDE_EXIT; see $REPORT.claude.err)"
fi

# 4. Validate the answer (schema-shaped, in code).
python3 - "$ANSWER.raw" "$ANSWER" "$HERE/response.schema.json" <<'EOF' || escalate "the responder's answer did not match response.schema.json"
import json, sys
raw, out, schema_path = sys.argv[1:4]
try:
    d = json.load(open(raw))
except json.JSONDecodeError as exc:
    print("claude output is not JSON:", exc, file=sys.stderr); sys.exit(1)
if d.get("subtype") != "success":
    print("claude result subtype:", d.get("subtype"), file=sys.stderr); sys.exit(1)
ans = d.get("structured_output")
if not isinstance(ans, dict):
    # Fallback: the model answered in text with a fenced JSON object.
    import re
    m = re.search(r"```json\s*(\{.*?\})\s*```", str(d.get("result") or ""), re.S)
    try:
        ans = json.loads(m.group(1)) if m else None
    except json.JSONDecodeError:
        ans = None
schema = json.load(open(schema_path))
if not isinstance(ans, dict): print("no JSON object in the answer", file=sys.stderr); sys.exit(1)
for key in schema["required"]:
    if key not in ans: print("missing", key, file=sys.stderr); sys.exit(1)
if ans["proposed_action"] not in schema["properties"]["proposed_action"]["enum"]: sys.exit(1)
if not (0 <= float(ans["confidence"]) <= 1): sys.exit(1)
ans["_cost_usd"] = d.get("total_cost_usd"); ans["_turns"] = d.get("num_turns")
json.dump(ans, open(out, "w"), indent=2)
print(json.dumps(ans, indent=2))
EOF
ACTION="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['proposed_action'])" "$ANSWER")"
CONF="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['confidence'])" "$ANSWER")"
say "proposed: $ACTION (confidence $CONF)"

# 5. Policy: is the action automatic, and is the model confident enough?
AUTO="$(policy "actions.$ACTION.automatic")"
NEED="$(policy "actions.$ACTION.requires_confidence")"
if [ "$AUTO" != "true" ]; then escalate "action '$ACTION' is not automatic under autonomy-policy.yaml"; fi
if python3 -c "import sys; sys.exit(0 if float('$CONF') < float('${NEED:-1}') else 1)"; then
  escalate "confidence $CONF is below the $NEED required for '$ACTION'"
fi

# 6. Execute the bounded action.
case "$ACTION" in
  clear_demo_fault)
    grep -q "InjectedFault" "$EVIDENCE" || escalate "clear_demo_fault proposed but the evidence shows no InjectedFault"
    say "action: clearing the demo fault via POST /debug/fault"
    curl -fsS -X POST "$API/debug/fault" -H 'Content-Type: application/json' -d '{"card_move_fails": false}' | tee -a "$REPORT.log"; echo
    ;;
  fix_in_worktree)
    if git -C "$WT" diff --quiet && git -C "$WT" status --porcelain | grep -q . ; then :; fi
    if [ -z "$(git -C "$WT" status --porcelain)" ]; then escalate "fix_in_worktree proposed but the worktree has no changes"; fi
    say "action: running the backend unit tests in the worktree"
    ( cd "$WT/backend" && uv run pytest -q 2>&1 | tail -3 | tee -a "$REPORT.log" ) || escalate "unit tests failed in the worktree"
    git -C "$WT" add -A && git -C "$WT" -c user.name=oncall-responder -c user.email=oncall@localhost commit -q -m "oncall: proposed fix for $ALERT ($TS)"
    say "committed on $BRANCH (never pushed); a human reviews the diff"
    ;;
esac

# 7. Verify recovery.
set +e
"$HERE/verify-recovery.sh" "$ALERT" 180 | tee -a "$REPORT.log"
VERIFIED=$?
set -e

# 8. Report.
{
  if [ "$VERIFIED" = 0 ]; then echo "# RECOVERED — $ALERT ($TS)"; else echo "# NEEDS HUMAN — $ALERT ($TS): action taken but recovery not verified"; fi
  echo
  echo "- action: \`$ACTION\` (automatic under policy, confidence $CONF)"
  [ "$ACTION" = fix_in_worktree ] && echo "- branch: \`$BRANCH\` in \`$WT\` — review with \`git -C $ROOT diff main..$BRANCH\`"
  echo "- cost: \$$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(round(d.get('_cost_usd') or 0, 4))" "$ANSWER") over $(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('_turns'))" "$ANSWER") turns"
  echo
  echo "## Responder answer"; echo '```json'; cat "$ANSWER"; echo; echo '```'
  echo
  echo "## Run log"; echo '```'; cat "$REPORT.log"; echo '```'
  echo
  echo "## Evidence"; echo; cat "$EVIDENCE"
} > "$REPORT"
say "report: $REPORT"
[ "$VERIFIED" = 0 ]
