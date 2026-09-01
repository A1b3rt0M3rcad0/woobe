from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[5]
AGENT_MODELS = PROJECT_ROOT / "src" / "modules" / "agent" / "infra" / "database" / "models.py"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations" / "versions"

AGENT_SCHEMA_TABLES: dict[str, str] = {
    "provider_credentials": "agent",
    "agents": "agent",
    "agent_prompts": "agent",
    "agent_contracts": "agent",
    "agent_model_configs": "agent",
    "agent_releases": "agent",
    "agent_release_tests": "agent",
    "document_collections": "agent",
    "agent_collections": "agent",
    "documents": "agent",
    "document_chunks": "agent",
    "knowledge_versions": "agent",
    "sessions": "agent",
    "messages": "agent",
    "ask_jobs": "agent",
    "tools": "agent",
    "tool_secrets": "agent",
    "agent_outbox_events": "agent",
    "agent_inbox_events": "agent",
}

def collect_current_schema_assignments() -> dict[str, str]:
    """Read models.py and return {tablename: schema} from __table_args__."""
    if not AGENT_MODELS.exists():
        raise FileNotFoundError(f"Models file not found: {AGENT_MODELS}")

    text = AGENT_MODELS.read_text(encoding="utf-8")
    tree = ast.parse(text)
    assignments: dict[str, str] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        table_name: str | None = None
        schema: str | None = None
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "__tablename__":
                        if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                            table_name = item.value.value
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "__table_args__":
                        args = item.value
                        if isinstance(args, ast.Dict):
                            for key, val in zip(args.keys, args.values):
                                if isinstance(key, ast.Constant) and key.value == "schema":
                                    if isinstance(val, ast.Constant):
                                        schema = val.value
                        elif isinstance(args, ast.Tuple):
                            for elt in args.elts:
                                if isinstance(elt, ast.Dict):
                                    for key, val in zip(elt.keys, elt.values):
                                        if isinstance(key, ast.Constant) and key.value == "schema":
                                            if isinstance(val, ast.Constant):
                                                schema = val.value
        if table_name and schema:
            assignments[table_name] = schema

    return assignments


def get_migration_revisions() -> list[str]:
    """Return sorted list of revision IDs from migration files."""
    if not MIGRATIONS_DIR.exists():
        return []
    revisions: list[str] = []
    for py_file in sorted(MIGRATIONS_DIR.glob("*.py")):
        text = py_file.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "revision":
                        if isinstance(node.value, ast.Constant):
                            revisions.append(str(node.value.value))
    return revisions


def detect_pending_migrations() -> list[str]:
    """Check for gaps in migration chain by verifying revises/head.

    Returns list of revisions with no dependent (orphan heads).
    """
    revisions = get_migration_revisions()
    all_revisions = set(r for r in revisions if r)
    has_dependent: set[str] = set()
    for py_file in sorted(MIGRATIONS_DIR.glob("*.py")):
        text = py_file.read_text(encoding="utf-8")
        tree = ast.parse(text)
        down_rev = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "down_revision":
                        if isinstance(node.value, ast.Constant):
                            down_rev = str(node.value.value)
        if down_rev and down_rev in all_revisions:
            has_dependent.add(down_rev)

    orphans = all_revisions - has_dependent
    if not revisions:
        return []
    expected_head = revisions[-1]
    return [r for r in orphans if r != expected_head]


def check_target_table_conflicts() -> list[str]:
    """Detect tables in schema='agent' that are NOT expected per the table map.

    Returns list of unexpected table names found in agent schema.
    """
    assignments = collect_current_schema_assignments()
    expected_agent_tables = {
        t for t, s in assignments.items() if s == "agent"
    }
    canonical_agent = set(AGENT_SCHEMA_TABLES.keys())
    unexpected = expected_agent_tables - canonical_agent
    return list(unexpected)


def capture_preflight_snapshot() -> dict[str, Any]:
    """Return a deterministic pre-move snapshot for specs 006-008.

    Returns:
        dict with:
        - 'table_schemas': current {tablename: schema} assignment
        - 'alembic_head': last revision in versions/
        - 'expected_move_count': number of tables NOT yet in agent schema
        - 'unexpected_agent_tables': conflicts in agent schema
        - 'pending_migrations': orphan revisions not at head
        - 'agent_schema_created_by_migration': which migration creates agent schema
    """
    assignments = collect_current_schema_assignments()
    revisions = get_migration_revisions()
    conflicting = check_target_table_conflicts()
    pending = detect_pending_migrations()

    tables_to_move = [t for t, s in assignments.items() if s in ("ai", "knowledge", "runtime")]

    return {
        "table_schemas": assignments,
        "alembic_head": revisions[-1] if revisions else None,
        "all_revisions": revisions,
        "tables_to_move": tables_to_move,
        "expected_move_count": len(tables_to_move),
        "unexpected_agent_tables": conflicting,
        "pending_migrations": pending,
        "agent_schema_created_by_migration": "0013",
        "total_agent_tables": len(assignments),
    }
