"""Seed demo customer via the API.

Usage:
    uv run python scripts/seed_customer.py

Creates idempotently:
  - User:     customer@gmail.com / customer
  - Org:      Customer Corp
  - Project:  Demo Project
  - Agent:    Demo Agent (GPT-4o)
  - API Key:  sk-demo-...
"""

import json
import sys
import urllib.error
import urllib.request

API = "http://localhost:8000"


def req(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            err = json.loads(body)
        except json.JSONDecodeError:
            err = {"message": body.decode()}
        if e.code == 409:
            return {"_skipped": True}
        print(f"  {method} {path} -> {e.code}: {err.get('message', err)}")
        sys.exit(1)


def seed() -> None:
    print("Seeding demo customer...\n")

    # 1. Register (creates user + org in one call)
    reg = req("POST", "/identity/auth/register", {
        "email": "customer@gmail.com",
        "password": "customer",
        "organization_name": "Customer Corp",
    })
    if reg.get("_skipped"):
        print("  User already exists — skipping registration")
        print("  (Login manually to get a fresh token)")
        return
    token = reg["data"]["token"]
    user = reg["data"]["user"]
    print(f"  User created:  {user['id']}  {user['email']}")

    # 2. Look up org
    orgs = req("GET", "/identity/organizations", token=token)
    org = orgs["data"][0] if isinstance(orgs.get("data"), list) else orgs["data"]
    org_id = org["id"]
    print(f"  Org active:    {org_id}  {org['name']}")

    # 3. Create project
    project = req("POST", "/core/projects", {
        "organization_id": org_id,
        "name": "Demo Project",
        "slug": "demo-project",
    }, token=token)
    if project.get("_skipped"):
        print("  Project already exists — skipping")
    else:
        proj = project["data"]
        print(f"  Project:       {proj['id']}  {proj['name']}")

    # 4. Create agent
    proj_id = project.get("data", {}).get("id") or project.get("id")
    agent = req("POST", "/ai/agents", {
        "project_id": proj_id,
        "name": "Demo Agent",
        "provider": "openai",
        "model": "gpt-4o",
        "system_prompt": "You are a helpful AI assistant.",
        "description": "Default demo agent for ProjectRAI",
        "temperature": 0.7,
        "max_output_tokens": 2048,
        "settings": {"session_mode": "chat"},
    }, token=token)
    if agent.get("_skipped"):
        print("  Agent already exists — skipping")
    else:
        a = agent["data"]
        print(f"  Agent created: {a['id']}  {a['name']}  ({a['provider']}/{a['model']})")

    # 5. Create API key
    api_key = req("POST", f"/core/projects/{proj_id}/api-keys", {
        "name": "Demo API Key",
        "scopes": ["ask", "sessions"],
    }, token=token)
    if api_key.get("_skipped"):
        print("  API Key already exists — skipping")
    else:
        k = api_key["data"]
        print(f"  API Key:       {k['key_prefix']}...")

    print("\nSeed complete!")
    print("  Login: customer@gmail.com / customer")
    print("  Dashboard: http://localhost:5173/dashboard")
    print("  API: http://localhost:8000")


if __name__ == "__main__":
    try:
        health = json.loads(urllib.request.urlopen(f"{API}/health").read())
        print(f"API {API} — {health}\n")
    except Exception as e:
        print(f"API not reachable at {API}: {e}")
        print("Make sure docker compose is running.")
        sys.exit(1)

    seed()
