"""Exercise release identity with real temporary Git histories, without publishing."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "automatic_release", ROOT / "scripts/release/resolve_auto_release.py"
)
auto = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auto)
REPO = "owner/woobe"


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def commit(message, version=None):
    if version is not None:
        Path("VERSION").write_text(version + "\n")
    else:
        path = Path("changes")
        path.write_text(
            path.read_text() + message + "\n" if path.exists() else message + "\n"
        )
    command("git", "add", ".")
    command("git", "commit", "-m", message)
    head = command("git", "rev-parse", "HEAD")
    command("git", "update-ref", "refs/remotes/origin/master", head)
    return head


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    command("git", "init", "-b", "master")
    command("git", "config", "user.email", "test@example.invalid")
    command("git", "config", "user.name", "Test")
    command("git", "config", "commit.gpgsign", "false")
    commit("chore(release): prepare Woobe v0.12.1", "0.12.1")
    command("git", "tag", "v0.12.1")
    return tmp_path


def record(version, complete=True):
    return {
        "tag_name": "v" + version,
        "draft": False,
        "assets": [{"name": "release-manifest.json"}] if complete else [],
    }


def metadata(releases=None, pulls=None):
    releases = [record("0.12.1")] if releases is None else releases
    return patch.object(
        auto,
        "api_pages",
        side_effect=lambda _, endpoint: (
            releases if endpoint.startswith("releases?") else (pulls or [])
        ),
    )


def pending(version, owner=REPO):
    return {
        "base": {"ref": "master"},
        "head": {"ref": "release/" + version, "repo": {"full_name": owner}},
    }


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("fix(agent): preserve bindings", "0.12.2"),
        ("feat(network): introduce closures", "0.13.0"),
        ("fix(runtime)!: replace incompatible contract", "0.13.0"),
        (
            "refactor(runtime): new contract\n\nBREAKING CHANGE: changed wire format",
            "0.13.0",
        ),
        ("docs(cli): clarify usage", "0.12.2"),
        ("Merge pull request #12 from owner/fix", "0.12.2"),
    ],
)
def test_reviewed_commits_calculate_next_version(repo, message, expected):
    source = commit(message)
    before = Path("VERSION").read_bytes()
    with metadata():
        result = auto.resolve(REPO, source=source, event="push")
    assert result["version"] == expected and result["skip"] == "false"
    assert Path("VERSION").read_bytes() == before
    assert command("git", "status", "--porcelain") == ""


def test_breaking_stable_release_advances_major():
    assert auto.bump("1.4.5", "feat(api)!: replace contract") == "2.0.0"
    assert auto.bump("1.4.5", "feat(api): add contract") == "1.5.0"
    assert auto.bump("1.4.5", "fix(api): correct validation") == "1.4.6"
    assert auto.bump("1.4.5-rc.1", "fix(api): correct validation") == "1.4.5"


@pytest.mark.parametrize(
    "bad", ["01.2.3", "1.02.3", "1.2.03", "1.2.3-01", "v1.2.3", "1.2.3\n", "$(whoami)"]
)
def test_invalid_versions_cannot_enter_outputs(bad):
    with pytest.raises(ValueError):
        auto.version_key(bad)


def test_first_release_opens_a_version_sync_instead_of_fabricating_recovery(repo):
    with metadata(releases=[]):
        result = auto.resolve(REPO)
    assert result["version"] == "0.12.2"
    assert result["release_exists"] == "false"


def test_release_merge_push_does_not_create_another_release(repo):
    commit("fix(agent): recover original receipt")
    source = commit("chore(release): prepare Woobe v0.12.2", "0.12.2")
    command("git", "tag", "v0.12.2")
    with metadata(releases=[record("0.12.1"), record("0.12.2")]):
        result = auto.resolve(REPO, source=source, event="push")
    assert result["skip"] == "true"
    assert result["version"] == "0.12.2"


def test_stale_push_skips_without_remote_writes_or_metadata_reads(repo):
    older = commit("fix(agent): old fix")
    commit("fix(network): newer fix")
    with patch.object(auto, "api_pages") as api:
        result = auto.resolve(REPO, source=older, event="push")
    assert result["skip"] == "true"
    api.assert_not_called()


def test_failed_publication_recovers_exact_canonical_version_after_new_work(repo):
    commit("chore(release): prepare Woobe v0.12.2", "0.12.2")
    commit("feat(agent): work after interrupted publication")
    with metadata():
        result = auto.resolve(REPO)
    assert result["version"] == "0.12.2" and result["skip"] == "false"
    assert "post-merge" in result["reason"]


def test_incomplete_release_is_repaired_before_another_version(repo):
    commit("fix(agent): newer work")
    with metadata(releases=[record("0.12.1", complete=False)]):
        result = auto.resolve(REPO)
    assert result["version"] == "0.12.1"
    assert result["already_published"] == "false" and result["release_exists"] == "true"


def test_existing_same_repo_release_pr_is_resumed_and_fork_is_ignored(repo):
    commit("fix(agent): newer work")
    with metadata(pulls=[pending("0.12.2"), pending("0.13.0", "fork/woobe")]):
        result = auto.resolve(REPO)
    assert result["version"] == "0.12.2"
    assert "existing release PR" in result["reason"]


def test_ambiguous_release_prs_do_not_reserve_a_third_version(repo):
    with metadata(pulls=[pending("0.12.2"), pending("0.13.0")]):
        with pytest.raises(ValueError, match="Multiple"):
            auto.resolve(REPO)


def test_old_release_pr_is_not_automatically_reused(repo):
    with metadata(pulls=[pending("0.12.1")]):
        with pytest.raises(ValueError, match="obsolete"):
            auto.resolve(REPO)


def test_manual_exact_version_and_published_recovery_are_preserved(repo):
    with metadata():
        result = auto.resolve(REPO, requested="0.12.1")
    assert result["release_exists"] == "true" and result["skip"] == "false"
    with metadata():
        assert auto.resolve(REPO, requested="0.15.0")["version"] == "0.15.0"


def test_unknown_github_state_cannot_be_treated_as_no_releases(repo):
    with patch.object(
        auto, "api_pages", side_effect=subprocess.CalledProcessError(1, "gh")
    ):
        with pytest.raises(subprocess.CalledProcessError):
            auto.resolve(REPO)


def test_master_incompatible_with_latest_tag_is_blocked(repo):
    command("git", "checkout", "--orphan", "unrelated")
    command("git", "rm", "-rf", ".")
    commit("fix(agent): unrelated history", "0.12.1")
    with metadata():
        with pytest.raises(ValueError, match="does not include"):
            auto.resolve(REPO)


def test_published_tag_with_wrong_canonical_version_is_blocked(repo):
    command("git", "tag", "v0.12.2")
    commit("fix(agent): newer work", "0.12.2")
    with metadata(releases=[record("0.12.2")]):
        with pytest.raises(ValueError, match="canonical VERSION"):
            auto.resolve(REPO)


def test_higher_impact_concurrent_merge_cannot_receive_patch_label(repo):
    commit("fix(agent): patch planned")
    with metadata():
        auto.verify_coverage(REPO, "0.12.2")
    commit("feat(network): concurrent feature")
    with metadata():
        with pytest.raises(ValueError, match="require 0.13.0"):
            auto.verify_coverage(REPO, "0.12.2")
    with metadata():
        auto.verify_coverage(REPO, "0.13.0")


def test_metadata_pagination_includes_later_pages_and_rejects_bad_shapes():
    with patch.object(
        auto,
        "command",
        return_value='[{"tag_name":"v0.12.0"}]\n[{"tag_name":"v0.12.1"}]',
    ) as cmd:
        assert len(auto.api_pages(REPO, "releases?per_page=100")) == 2
        assert "--paginate" in cmd.call_args.args and "@json" in cmd.call_args.args
    with patch.object(auto, "command", return_value='{"message":"unauthorized"}'):
        with pytest.raises(ValueError, match="Unexpected"):
            auto.api_pages(REPO, "releases?per_page=100")


def test_version_preparation_synchronizes_real_mirrors_without_dependency_updates(
    tmp_path,
):
    gate_spec = importlib.util.spec_from_file_location(
        "release_gate", ROOT / "scripts/release/orchestrate_release_pr.py"
    )
    gate = importlib.util.module_from_spec(gate_spec)
    gate_spec.loader.exec_module(gate)
    paths = gate.ALLOWED_RELEASE_PATHS | {
        "scripts/release/set_platform_version.py",
        "scripts/ci/check_package_versions.py",
    }
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    domain = tmp_path / "agent-release.yaml"
    domain.write_text("kind: Agent\nversion: 1.0.0\n")
    locks = [
        f"packages/woobe-{unit}/package-lock.json" for unit in ("frontend", "embed")
    ]
    before = {
        path: json.loads((tmp_path / path).read_text())["packages"] for path in locks
    }
    uv_before = tomllib.loads((tmp_path / "uv.lock").read_text())["package"]
    command(
        sys.executable,
        str(tmp_path / "scripts/release/set_platform_version.py"),
        "0.13.0",
    )
    command(sys.executable, str(tmp_path / "scripts/ci/check_package_versions.py"))
    for path in locks:
        after = json.loads((tmp_path / path).read_text())["packages"]
        assert {k: v for k, v in after.items() if k} == {
            k: v for k, v in before[path].items() if k
        }
    uv_after = tomllib.loads((tmp_path / "uv.lock").read_text())["package"]
    assert [p for p in uv_after if p["name"] != "woobe"] == [
        p for p in uv_before if p["name"] != "woobe"
    ]
    assert domain.read_text() == "kind: Agent\nversion: 1.0.0\n"
