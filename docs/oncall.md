# On-call responder

When an alert fires, an agent wakes up, looks at the evidence, decides, acts
within a written policy, and checks that the incident is over. A person
reads a report, not a pager.

```
Prometheus ──alert──► Alertmanager ──webhook──► oncall/server.py (host, :9000)
                                                      │ one responder per alert name per 10 min
                                                      ▼
                                              oncall/responder.sh
   collect-evidence.sh ─► evidence packet (read-only, bounded, no secrets)
   git worktree add      ─► isolated checkout on branch oncall/<ts>-<alert>
   claude -p … --json-schema response.schema.json ─► {diagnosis, root_cause, proposed_action, confidence, …}
   autonomy-policy.yaml  ─► is the action automatic? is confidence enough?   (enforced in bash, not by the model)
   action                ─► clear_demo_fault | fix_in_worktree (tests must pass, commit on the branch, never pushed)
   verify-recovery.sh    ─► alert inactive + condition cleared + smoke test
   oncall/reports/<ts>-<alert>.md ─► RECOVERED or NEEDS HUMAN
```

Everything lives in [`oncall/`](../oncall/):

| File | Role |
|---|---|
| `server.py` | Alertmanager webhook receiver (stdlib only). Starts one responder per firing alert name, with a cooldown; logs resolved notifications. |
| `responder.sh` | The loop above. Owns every permission decision. |
| `collect-evidence.sh` | Allowlisted, read-only queries to Prometheus, Loki, Tempo, `docker compose ps` and git; capped at 40 kB; never environment variables, headers, bodies or e-mails. |
| `prompt.md` | What the model is told. |
| `response.schema.json` | The only shape of answer accepted. |
| `autonomy-policy.yaml` | What is automatic, what needs a human, turn and dollar caps, cooldown. |
| `verify-recovery.sh` | Re-evaluates the alert condition and runs `scripts/smoke.sh`. |
| `demo.sh` | The end-to-end demonstration (`make demo-oncall`). |

## The model's box

The responder runs headless Claude Code (`claude -p`) with:

- `--safe-mode`: no CLAUDE.md, hooks, plugins or MCP servers;
- `--tools Read,Grep,Glob,Edit,Write,Bash` and `--allowedTools` limited to
  reading, editing inside the worktree, `uv run pytest`, and read-only git
  commands; `--permission-mode dontAsk` denies everything else instead of
  prompting;
- `--max-turns` and `--max-budget-usd` from the policy;
- a scrubbed environment: `JWT_SECRET`, `DATABASE_URL`, `GEMINI_API_KEY`
  and the Render hooks are unset; the live API, database and stores are not
  addressed anywhere in the prompt;
- the worktree as its working directory and `--add-dir` scope. The main
  checkout, `.env`, `render.yaml` and the workflows are outside it.

Its answer must validate against `response.schema.json` (checked in
Python); anything else is treated as *escalate*. Two things learned the
hard way about `--json-schema`: the model answers through a
`StructuredOutput` tool, which must not be filtered out (do not pass
`--tools`), and a schema that carries a `$schema` header makes Claude Code
drop that tool silently, so the file has none. The proposed action is then
looked up in `autonomy-policy.yaml`: only `clear_demo_fault` and
`fix_in_worktree` are automatic, each with a minimum confidence, and
`clear_demo_fault` is additionally refused unless the evidence packet
itself contains `InjectedFault`. `restart_backend` and `escalate` always
end in a NEEDS HUMAN report. The model never pushes, deploys, or touches
containers; the code around it does one allowlisted thing and then
verifies.

## The demo

```sh
make observe        # app + observability stack
make seed           # demo board
make demo-oncall    # the whole loop; prints the report at the end
```

`demo.sh` starts the receiver, runs `observability/demo-alert.sh --keep`
(card moves start failing with `InjectedFault`, KanbanApiErrors fires in
about a minute), and waits for the report. Alertmanager delivers the alert
after its 10 s `group_wait`; the responder then collects evidence, reasons
for a minute or two, proposes `clear_demo_fault`, the responder clears the
fault, and `verify-recovery.sh` watches the alert go inactive and the smoke
test pass. A recorded run is in [`oncall-demo.md`](oncall-demo.md).

To exercise the escalation path, trigger KanbanApiDown instead
(`docker compose stop backend` while the receiver runs): the only honest
proposal is `restart_backend`, which is not automatic, so the report starts
with NEEDS HUMAN and names the action.

## Reports and clean-up

`oncall/reports/<timestamp>-<alert>.md` holds the verdict, the answer, the
run log and the evidence; `oncall/worktrees/<timestamp>-<alert>/` and the
branch `oncall/<timestamp>-<alert>` hold any proposed code change for
review (`git diff main..oncall/<…>`). `make oncall-clean` removes worktrees
and branches; reports stay. All three directories are git-ignored.

## Why this shape

- **Evidence first, bounded, read-only.** The model never queries anything
  itself; it reads a packet that a script assembled from allowlisted
  queries. What it cannot see, it cannot leak, and the packet is the same
  thing a human would read.
- **Permissions in code, not in prose.** The tool allowlist, the deny-by-
  default permission mode, the scrubbed environment and the policy lookup
  are all outside the model. The prompt repeats the rules for clarity, but
  nothing depends on the model obeying them.
- **Small automatic actions, everything else to a human.** Clearing a demo
  switch and committing a tested change on an un-pushed branch are
  reversible and local. Restarts and deploys are proposals.
- **Verification is observation.** Recovery means the alert condition is
  false in Prometheus and the smoke test passes, not that the model said
  so.
