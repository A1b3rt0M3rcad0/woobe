from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request


def request_json(opener, method: str, url: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Content-Type", "application/json")
    try:
        with opener.open(request) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = raw
        raise SystemExit(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create the initial Woobe Community demo owner without hard-coded credentials"
    )
    parser.add_argument("--api", default=os.getenv("WOOBE_DEMO_API", "http://localhost:8000"))
    parser.add_argument("--email", default=os.getenv("WOOBE_DEMO_EMAIL"))
    parser.add_argument("--password", default=os.getenv("WOOBE_DEMO_PASSWORD"))
    args = parser.parse_args()

    if not args.email or not args.password:
        raise SystemExit(
            "Provide --email/--password or WOOBE_DEMO_EMAIL/WOOBE_DEMO_PASSWORD. "
            "Woobe does not ship fixed demo credentials."
        )

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    status = request_json(opener, "GET", f"{args.api}/identity/instance/status")["data"]
    if status["edition"] != "community":
        raise SystemExit("seed_demo.py is intended for Woobe Community")
    if status["initialized"]:
        raise SystemExit("Woobe instance is already initialized; refusing to create another owner")
    if status["requires_existing_owner_bootstrap"]:
        raise SystemExit(
            "Existing users were detected. Use scripts/bootstrap_existing_instance.py instead."
        )

    result = request_json(
        opener,
        "POST",
        f"{args.api}/identity/instance/bootstrap",
        {"email": args.email, "password": args.password},
    )
    workspace = result.get("data", {}).get("workspace", {})
    print("Woobe Community bootstrap completed")
    print(f"Owner: {args.email}")
    if workspace.get("id"):
        print(f"Workspace: {workspace['id']}")


if __name__ == "__main__":
    main()
