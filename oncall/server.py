"""Alertmanager webhook receiver that starts the on-call responder.

    python3 oncall/server.py            # listens on :9000, foreground

Alertmanager (observability/alertmanager.yml) POSTs its payload to
/alert. For every *firing* alert this starts `oncall/responder.sh
<alertname> <payload.json>` in a background thread — at most once per alert
name per `cooldown_seconds` (autonomy-policy.yaml), so a flapping alert
cannot spawn a pile of agents. Resolved notifications are logged only.

Standard library only; runs on the host because the responder needs the
`claude` CLI and the repository. No authentication: it binds to localhost
and the Compose network reaches it via host.docker.internal.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESPONDER = HERE / "responder.sh"
PAYLOADS = HERE / "payloads"
PORT = int(os.environ.get("ONCALL_PORT", "9000"))


def cooldown_seconds() -> int:
    # Tiny YAML read without a YAML dependency: the key is on its own line.
    for line in (HERE / "autonomy-policy.yaml").read_text().splitlines():
        if line.strip().startswith("cooldown_seconds:"):
            return int(line.split(":", 1)[1].split("#")[0].strip())
    return 600


COOLDOWN = cooldown_seconds()
_last_run: dict[str, float] = {}
_lock = threading.Lock()


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def start_responder(alertname: str, payload: dict) -> None:
    PAYLOADS.mkdir(exist_ok=True)
    path = PAYLOADS / f"{int(time.time())}-{alertname}.json"
    path.write_text(json.dumps(payload, indent=2))
    log(f"starting responder for {alertname} ({path.name})")
    proc = subprocess.run([str(RESPONDER), alertname, str(path)], cwd=HERE.parent, text=True, capture_output=True)
    log(f"responder for {alertname} finished with exit {proc.returncode}")
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
    for line in tail:
        log(f"  {line}")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 (http.server API)
        if self.path != "/alert":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_error(400, "invalid JSON")
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

        firing = {a["labels"].get("alertname", "?") for a in payload.get("alerts", []) if a.get("status") == "firing"}
        resolved = {a["labels"].get("alertname", "?") for a in payload.get("alerts", []) if a.get("status") == "resolved"}
        for name in sorted(resolved):
            log(f"resolved: {name}")
        for name in sorted(firing):
            with _lock:
                last = _last_run.get(name, 0.0)
                if time.time() - last < COOLDOWN:
                    log(f"firing: {name} — within cooldown ({int(time.time() - last)}s ago), not starting another responder")
                    continue
                _last_run[name] = time.time()
            threading.Thread(target=start_responder, args=(name, payload), daemon=True).start()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_error(404)

    def log_message(self, format: str, *args) -> None:  # quieter than the default
        pass


def main() -> None:
    if not RESPONDER.exists():
        sys.exit(f"missing {RESPONDER}")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log(f"on-call webhook listening on :{PORT} (POST /alert); cooldown {COOLDOWN}s per alert")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("stopping")


if __name__ == "__main__":
    main()
