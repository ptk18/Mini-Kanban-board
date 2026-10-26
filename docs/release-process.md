# Release process

```
 pull request ──► CI (lint · unit · integration · images · e2e) ──► merge to main
                                                                         │
                                                      CI on main green ──┤
                                                                         ▼
                                            Deploy workflow: dev (automatic)
                                            scripts/deploy-vercel.sh dev → smoke test
                                                                         │
                                               try it on dev, decide ────┤
                                                                         ▼
                                   Deploy workflow: production (manual "Run workflow")
                                   CI-green check → [approval] → scripts/deploy-vercel.sh prod → smoke test
```

## 1. Change

Work on a branch, open a pull request. [CI](testing.md#ci) must be green;
`main` should be protected so it cannot merge otherwise. Squash or merge —
either way `main` moves to one commit that CI has proven.

## 2. Dev deploys itself

When the CI run for the new `main` commit succeeds, the *Deploy* workflow
starts (`workflow_run` trigger), checks out **that exact sha** and runs
`scripts/deploy-vercel.sh dev`, which deploys `mini-kanban-api-dev` and
`mini-kanban-web-dev` and ends with `scripts/smoke.sh` against their URLs
until `/health` reports that sha and `/login` renders. A failed smoke test
fails the workflow and shows up on the commit; dev is then the only thing
affected.

Pushes never deploy by themselves: the Vercel projects are deployed by
the CLI from this workflow, not connected to Git. Only this workflow (or
the same script run by hand) deploys.

## 3. Production is a decision

*Actions → Deploy → Run workflow*, `environment: production`, `ref` empty.
The job

1. refuses any commit that does not have a successful CI run;
2. waits for approval if the `production` GitHub environment has required
   reviewers (recommended);
3. runs `scripts/deploy-vercel.sh prod` on that sha;
4. smoke tests the production URLs the same way.

Promote only a sha that already ran on dev — normally the current `main`.

## 4. Rollback

Two equivalent ways.

- **From Vercel (instant):** project → *Deployments* → the previous good
  production deployment → *Promote to Production*. No rebuild; do it for
  `mini-kanban-api` and, if needed, `mini-kanban-web`.
- **From GitHub (a few minutes):** *Run workflow*, `environment: production`,
  `ref: <last known-good sha>`. The script deploys that commit, and the
  smoke test confirms `/health` reports it. The same works for dev.

Database migrations are forward-only. A rollback of the code leaves the
schema at the newer revision, so a migration must stay compatible with the
previous release (add columns as nullable or with defaults, never drop or
rename in the same release that stops using them). If a migration itself
must be undone: `uv run alembic downgrade <revision>` against the database
URL (`DEPLOY_DATABASE_URL`).

## 5. What a release is

`main`'s commit sha. `/health` returns it as `version`, the smoke test asserts
it, and each Vercel deployment carries it as `APP_VERSION`, so "what is running where" is
always answerable without guessing. There are no version tags; if you want
them, tag the sha after the production smoke test passes.
