# Deployment

The app deploys for free to [Vercel](https://vercel.com) as two projects
built from this repository, with Postgres hosted by Neon:

| Project | Directory | Runtime | Production URL |
|---|---|---|---|
| `mini-kanban-api` | `backend/` | Vercel Python runtime, FastAPI as one Vercel Function (Python 3.14 from `pyproject.toml` + `uv.lock`; `backend/vercel.json` sets a 30 s max duration) | `https://mini-kanban-api.vercel.app` |
| `mini-kanban-web` | `frontend/` | Next.js | `https://mini-kanban-web.vercel.app` |
| database | — | Neon Postgres (free, no expiry), created from Vercel's *Storage* tab | — |

The `-dev` twins (`mini-kanban-api-dev`, `mini-kanban-web-dev`) are the
**dev** environment that CD deploys automatically; production is a manual
run. See [`release-process.md`](release-process.md).

Nothing in the app is Vercel-specific: the FastAPI lifespan still runs
`alembic upgrade head` on a cold start, `/health` reports the deployed commit
(`APP_VERSION`, set by the deploy script), and the same images run under
Docker Compose.

## Deploy to Vercel

One-time, by the owner (about five minutes, no card):

1. **Vercel account.** Sign up at vercel.com with the GitHub account, Hobby
   plan. Create a token at <https://vercel.com/account/tokens> (scope: your
   account, no expiry or a long one).
2. **Database.** Vercel dashboard → *Storage* → *Create Database* → **Neon**
   (free plan, region close to `iad1` / Washington, D.C., where Vercel runs
   functions by default). Open it → *.env.local* tab → copy `DATABASE_URL`
   (the pooled one, it ends in `?sslmode=require`).
3. **Local `.env`** (repo root, git-ignored) gets two lines:

   ```sh
   VERCEL_TOKEN=...
   DEPLOY_DATABASE_URL=postgres://...?sslmode=require
   ```

   `OPENAI_API_KEY` is already there; it is copied to the API project.

Then one command does everything else: creates both projects, sets their
environment variables (secrets are passed on stdin, never printed),
deploys the API, deploys the frontend with the API's URL baked in, points
the API's `CORS_ORIGINS` at the frontend, redeploys the API, and runs the
smoke test:

```sh
scripts/deploy-vercel.sh prod      # or: dev
```

Optional demo data: `DATABASE_URL="$DEPLOY_DATABASE_URL" uv run --directory backend python scripts/seed.py`.

For CD from GitHub, add `VERCEL_TOKEN`, `DEPLOY_DATABASE_URL`
(+ optional `DEPLOY_DATABASE_URL_DEV`, e.g. a Neon branch, and
`OPENAI_API_KEY`) as repository secrets. Until `VERCEL_TOKEN` exists the
*Deploy* workflow logs "skipped" and stays green.

**Rollback:** *Actions → Deploy → Run workflow*, `environment: production`,
`ref: <known-good sha>`; or in Vercel, the project's *Deployments* →
previous deployment → *Promote to Production* (instant, no rebuild).

**Free-plan notes:** functions cold-start in a second or two after idle;
the Hobby plan is for non-commercial use; Neon's free compute suspends
after five idle minutes and wakes on the next query.

## Alternative: Render

The repository is also deploy-ready for [Render](https://render.com) as two
Docker web services plus a managed Postgres. Everything Render needs is
declared in [`render.yaml`](../render.yaml). This path was set aside because
the Render workspace used for this project had its free web services
suspended (free instance hours), so Render could create the database but
not the services; the steps below still apply to a workspace in good
standing.

### What gets deployed — all free

| Resource | Name | Plan | From |
|---|---|---|---|
| API | `mini-kanban-api-dev` | free web service | `backend/Dockerfile`; runs `alembic upgrade head` then uvicorn on `PORT=8000`; health check `/health` |
| Frontend | `mini-kanban-web-dev` | free web service | `frontend/Dockerfile`; `NEXT_PUBLIC_API_URL` baked in at build; health check `/login` |
| Postgres 17 | `mini-kanban-db-dev` | free (1 GB, **deleted 30 days after creation**) | `databases:` in `render.yaml` |

Everything in `render.yaml` is on a free plan, so applying the Blueprint
should not ask for a payment method. (An earlier version declared a paid
production database as well; that is what triggers Render's billing prompt.
A production environment is a later, paid decision — see the end of this
page.) Free web services sleep after 15 minutes without traffic and take
about a minute to wake; the smoke test allows for that.

#### Free database that does not expire

Render's free Postgres is deleted 30 days after creation (14-day grace).
For something that outlives a review window, use a free hosted Postgres
with no expiry, e.g. [Neon](https://neon.tech) (free tier, no card), and
point the API at it:

1. Create a Neon project (Postgres 17 is fine); copy its connection string
   (`postgres://user:password@host/dbname?sslmode=require`).
2. In `render.yaml`, replace the API's `DATABASE_URL` entry with
   `- key: DATABASE_URL` / `sync: false` and delete the `databases:` block
   (or, on an existing service, set `DATABASE_URL` in *Environment*).
3. Paste the Neon string when prompted. The backend accepts the
   `postgres://` scheme and the `sslmode` query parameter as-is; migrations
   run on the next deploy.

#### If the dashboard still asks for a card

Create the same three things by hand, no Blueprint needed:

1. *New → Postgres*: name `mini-kanban-db-dev`, plan **Free**, region of
   your choice (or skip this and use Neon as above).
2. *New → Web Service* → the repo → **Root Directory** `backend`, runtime
   **Docker**, plan **Free**, health check path `/health`, environment:
   `DATABASE_URL` (the database's *Internal* URL), `JWT_SECRET` (any 32+
   random characters), `CORS_ORIGINS` (the frontend URL from step 3),
   `OPENAI_API_KEY` (optional), `PORT=8000`. Auto-deploy **off**.
3. *New → Web Service* → the repo → **Root Directory** `frontend`, Docker,
   Free, health check `/login`, environment: `NEXT_PUBLIC_API_URL` (the API
   URL from step 2), `PORT=3000`. Auto-deploy **off**.

Then continue from step 4 below (deploy hooks into GitHub).

### One-time setup on Render (owner)

1. **Create a Render account** and connect the GitHub account that owns
   `ptk18/Mini-Kanban-board`.
2. **New → Blueprint**, pick the repository, branch `main`. Render reads
   `render.yaml` and lists the resources. The only prompt is
   `OPENAI_API_KEY` (marked `sync: false`); paste the key or leave it empty
   to run without the AI routes. `JWT_SECRET` is generated by Render
   (`generateValue: true`), `DATABASE_URL` is wired from the database.
   Apply.
3. **Check the names.** Each service's URL is `https://<name>.onrender.com`.
   If a name was already taken, Render appends a suffix; then edit the two
   cross-references in `render.yaml` (`CORS_ORIGINS` on the API,
   `NEXT_PUBLIC_API_URL` on the frontend) to the real URLs, commit, and
   let the Blueprint sync.
4. **Copy the deploy hooks.** For each of the two services: *Settings →
   Deploy Hook*. In GitHub, *Settings → Secrets and variables → Actions →
   New repository secret*:

   | Secret | Value |
   |---|---|
   | `RENDER_DEPLOY_HOOK_API_DEV` | deploy hook of `mini-kanban-api-dev` |
   | `RENDER_DEPLOY_HOOK_WEB_DEV` | deploy hook of `mini-kanban-web-dev` |

   and on the *Variables* tab:

   | Variable | Value |
   |---|---|
   | `DEV_API_URL` | `https://mini-kanban-api-dev.onrender.com` |
   | `DEV_WEB_URL` | `https://mini-kanban-web-dev.onrender.com` |

   (The `*_PROD` secrets and variables are only needed once a production
   environment exists; until then the manual production job skips green.)

   The hooks are secrets (anyone holding one can deploy); *Regenerate Hook*
   in Render if one leaks, then update the GitHub secret.
5. **Protect production** (recommended): GitHub *Settings → Environments →
   production → Required reviewers*. The manual production job then waits
   for an approval click.
6. **First deploy:** push to `main` (or re-run the latest *Deploy* workflow).
   Dev deploys and is smoke-tested automatically.
7. **Seed (optional):** Render's free plan has no shell, so seed from your
   machine against the dev database by temporarily adding your IP to
   `ipAllowList`, exporting the *External Database URL* and running
   `cd backend && uv run python scripts/seed.py`. Remove the IP afterwards.
8. Put the production URL in the README.

## Environment variables in production

| Variable | Set by | Notes |
|---|---|---|
| `DATABASE_URL` | Blueprint (`fromDatabase`) | Render gives `postgres://…`; the backend normalises it to `postgresql+psycopg://`. |
| `JWT_SECRET` | Blueprint (`generateValue`) | 256-bit random. Rotating it logs everyone out. |
| `CORS_ORIGINS` | Blueprint | The frontend's public URL. |
| `OPENAI_API_KEY` | you, at Blueprint apply | Empty → AI routes answer `503`. (`GEMINI_API_KEY` works as an alternative.) |
| `NEXT_PUBLIC_API_URL` | Blueprint, **build-time** | Render passes env vars as Docker build args; a change needs a redeploy to take effect. |
| `PORT` | Blueprint | `8000` (API) / `3000` (frontend) to match the Dockerfiles. |
| `RENDER_GIT_COMMIT` | Render | Reported by `/health` as `version`; the smoke test waits for it to match. |

No secret is in the repository. The deploy workflow holds only deploy hooks
and public URLs.

## Verifying a deployment

```sh
scripts/smoke.sh https://mini-kanban-api-dev.onrender.com https://mini-kanban-web-dev.onrender.com <sha>
```

polls `/health` until `{"status":"ok","version":"<sha>"}` (so it proves the
*new* build is live, not the old one still serving) and then checks the
frontend's `/login` answers `200`. The workflow runs exactly this after every
deploy; locally it also works against Docker Compose:

```sh
scripts/smoke.sh http://localhost:8000 http://localhost:3000
```

## Other platforms

Nothing is Render-specific except `render.yaml`. The two Dockerfiles, the
entrypoint that migrates on start, `PORT`, and `/health` are what any
container platform (Fly.io, Railway, Cloud Run, a VM with Compose) needs;
`docker-compose.yml` is a complete reference deployment.

### Adding a paid Render production environment later

A second environment needs its own database, and a workspace has only one
free Postgres. When that is wanted: add `mini-kanban-api-prod` /
`mini-kanban-web-prod` (free web services) and `mini-kanban-db-prod` on the
smallest paid plan (`0.1c-256mb`) to `render.yaml` with the same shape as
the dev entries, fill the `*_PROD` secrets and variables, and
`deploy.yml`'s manual production job takes over. Or keep production on
Neon too, which is free.
