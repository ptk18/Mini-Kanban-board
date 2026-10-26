"""The deployed version, read once from the environment.

``APP_VERSION`` wins (set by scripts/deploy-vercel.sh or a Docker build
arg); Vercel Git deployments set ``VERCEL_GIT_COMMIT_SHA`` and Render sets
``RENDER_GIT_COMMIT``; otherwise ``"dev"``. Reported by ``/health`` so the
post-deploy smoke test can confirm the new build is live, and attached to
every trace, metric and log as ``service.version``.
"""

import os


def app_version() -> str:
    return (
        os.environ.get("APP_VERSION")
        or os.environ.get("VERCEL_GIT_COMMIT_SHA")
        or os.environ.get("RENDER_GIT_COMMIT")
        or "dev"
    )
