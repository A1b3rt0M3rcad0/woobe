"""Runnable without the application stack: python -m unittest discover -s tests/unit -p test_release_orchestrator.py."""

from __future__ import annotations

import importlib.util
from itertools import count
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "release_gate", ROOT / "scripts/release/orchestrate_release_pr.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

REPO = "owner/woobe"
HEAD = "validated-head"
BRANCH = "release/0.12.0"


def runs(conclusion: str | None = "success") -> dict:
    return {
        name: {
            "id": index,
            "name": name,
            "path": f".github/workflows/{filename}",
            "head_sha": HEAD,
            "event": "pull_request",
            "status": "completed",
            "conclusion": conclusion,
            "created_at": "2026-09-25T17:54:04Z",
        }
        for index, (name, filename) in enumerate(gate.REQUIRED_WORKFLOWS.items(), 1)
    }


class ReleaseGateTests(unittest.TestCase):
    def test_prepare_workflow_supports_post_merge_recovery_and_end_to_end_status(self):
        workflow = (ROOT / ".github/workflows/prepare-release.yml").read_text()

        self.assertIn("Validate target version and resolve release state", workflow)
        self.assertIn('resume_finalization="true"', workflow)
        self.assertIn("resuming post-merge finalization", workflow)
        self.assertIn('gh release view "v$TARGET_VERSION"', workflow)
        self.assertIn("uses: ./.github/workflows/release-candidate.yml", workflow)
        self.assertNotIn("Create or verify immutable release tag", workflow)
        self.assertIn("uses: ./.github/workflows/release.yml", workflow)
        publisher = (ROOT / ".github/workflows/release.yml").read_text()
        self.assertIn("Preflight release version targets", publisher)
        self.assertIn("Create or verify immutable release tag", publisher)
        self.assertIn("needs: [publish, post-publish-smoke]", publisher)
        self.assertNotIn("dispatch_and_wait.py", workflow)
        self.assertIn("Verify completed release recovery", workflow)
        self.assertIn("release-manifest.json", workflow)
        self.assertIn("Branch $branch exists without an open or merged release PR", workflow)

    def test_workflow_summary_reports_only_completed_end_to_end_release(self):
        workflow = (ROOT / ".github/workflows/prepare-release.yml").read_text()
        step = workflow.split("      - name: Release orchestration summary\n", 1)[1]
        script = textwrap.dedent(step.split("        run: |\n", 1)[1])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "summary"
            subprocess.run(
                ["bash", "-e", "-c", script],
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "VERSION": "0.12.0",
                    "REVISION": "merge-sha",
                    "PR_NUMBER": "168",
                    "VALIDATED_HEAD_SHA": HEAD,
                    "VALIDATION_ID": "run-attempt:parent",
                    "RELEASE_URL": "https://example.test/release",
                    "RESUMED": "false",
                    "ALREADY_PUBLISHED": "false",
                    "GITHUB_STEP_SUMMARY": str(output),
                },
            )
            summary = output.read_text()
            self.assertIn("Revision: `merge-sha`", summary)
            self.assertIn("Candidate validation: `run-attempt:parent`", summary)
            self.assertIn("GitHub Release: https://example.test/release", summary)
            self.assertIn("all passed", summary)


    def test_publish_workflow_summary_renders_release_values_literally(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text()
        step = workflow.split("      - name: Release summary\n", 1)[1]
        script = textwrap.dedent(step.split("        run: |\n", 1)[1])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "summary"
            subprocess.run(
                ["bash", "-e", "-c", script],
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "VERSION": "0.12.0",
                    "REVISION": "merge-sha",
                    "VALIDATION_ID": "candidate-validation",
                    "RELEASE_URL": "https://example.test/release",
                    "GITHUB_STEP_SUMMARY": str(output),
                },
            )
            summary = output.read_text()
            self.assertIn("Revision: `merge-sha`", summary)
            self.assertIn("Candidate validation: `candidate-validation`", summary)
            self.assertIn("Git tag: `v0.12.0`", summary)

    def test_pagination_identity_and_same_second_run_order(self):
        old = runs()["Backend test suite"]
        new = dict(old, id=20, conclusion="action_required")
        unrelated = [
            dict(old, id=100, path=".github/workflows/other.yml"),
            dict(old, id=101, head_sha="other-head"),
            dict(old, id=102, event="push"),
        ]
        pages = [{"workflow_runs": [old, *unrelated]}, {"workflow_runs": [new]}]
        with patch.object(gate, "gh_json", return_value=pages) as api:
            self.assertEqual(gate.workflow_runs(REPO, HEAD), {old["name"]: new})
            self.assertIn("--paginate", api.call_args.args[0])
            self.assertIn("--slurp", api.call_args.args[0])

    def test_approval_is_waited_for_and_never_redispatched(self):
        blocked = runs("action_required")
        running = {name: dict(item, status="in_progress", conclusion=None)
                   for name, item in runs().items()}
        with (
            patch.object(gate, "workflow_runs", side_effect=[blocked, blocked, blocked, running, runs()]),
            patch.object(gate.time, "monotonic", side_effect=count()),
            patch.object(gate.time, "sleep") as sleep,
            patch.object(gate, "run") as command,
            patch.object(gate, "comment") as comment,
        ):
            gate.wait_for_green(REPO, 166, BRANCH, HEAD, 60)
            command.assert_not_called()
            self.assertEqual(sleep.call_count, 3)
            comment.assert_called_once()
            self.assertIn("Approve workflows to run", comment.call_args.args[2])

    def test_approval_and_missing_runs_cannot_pass_on_timeout(self):
        for snapshot in (runs("action_required"), {}):
            with (
                self.subTest(snapshot=snapshot),
                patch.object(gate, "dispatch_missing"),
                patch.object(gate, "workflow_runs", return_value=snapshot),
                patch.object(gate.time, "monotonic", side_effect=count()),
                patch.object(gate.time, "sleep"),
                patch.object(gate, "comment"),
                self.assertRaisesRegex(gate.ReleaseGateError, "Timed out"),
            ):
                gate.wait_for_green(REPO, 166, BRANCH, HEAD, 3)

    def test_real_failures_block_even_when_other_checks_are_missing(self):
        for conclusion in ("failure", "cancelled", "timed_out", "skipped", "neutral", None):
            failed = {"Backend test suite": runs(conclusion)["Backend test suite"]}
            with (
                self.subTest(conclusion=conclusion),
                patch.object(gate, "dispatch_missing"),
                patch.object(gate, "workflow_runs", return_value=failed),
                patch.object(gate.time, "sleep") as sleep,
                patch.object(gate, "comment"),
                self.assertRaisesRegex(gate.ReleaseGateError, "Required CI did not pass"),
            ):
                gate.wait_for_green(REPO, 166, BRANCH, HEAD, 60)
            sleep.assert_not_called()

    def test_only_missing_workflow_is_dispatched_with_its_pr_context(self):
        snapshot = runs("action_required")
        del snapshot["CLA acceptance"]
        with (
            patch.object(gate, "workflow_runs", return_value=snapshot),
            patch.object(gate.time, "monotonic", side_effect=count(0, 10)),
            patch.object(gate.time, "sleep"),
            patch.object(gate, "run") as command,
        ):
            gate.dispatch_missing(REPO, 166, BRANCH, HEAD)
            command.assert_called_once_with(
                ["gh", "workflow", "run", "cla.yml", "--repo", REPO,
                 "--ref", BRANCH, "-f", "pr_number=166"], capture=False,
            )

    def test_head_changed_during_final_fetch_is_validated_before_merge(self):
        new_head = "concurrent-head"
        args = SimpleNamespace(repo=REPO, pr=166, branch=BRANCH, version="0.12.0",
                               timeout_seconds=60, github_output=None)
        with (
            patch.object(gate, "parse_args", return_value=args),
            patch.object(gate, "checkout_release_branch", side_effect=[HEAD, new_head]),
            patch.object(gate, "refresh_from_master_if_needed", side_effect=[
                (HEAD, False), (new_head, False), (new_head, False), (new_head, False),
            ]),
            patch.object(gate, "pr", side_effect=[{"head": {"sha": HEAD}}, {"head": {"sha": new_head}}]),
            patch.object(gate, "wait_for_green") as wait,
            patch.object(gate, "merge_release", return_value="merge-sha") as merge,
            patch.object(gate, "comment"),
        ):
            self.assertEqual(gate.main(), 0)
            self.assertEqual([call.args[3] for call in wait.call_args_list], [HEAD, new_head])
            merge.assert_called_once_with(REPO, 166, new_head, "0.12.0")

    def test_wrong_base_or_release_branch_is_rejected_before_checkout(self):
        for base, branch in (("development", BRANCH), ("master", "release/0.13.0")):
            with (
                self.subTest(base=base, branch=branch),
                patch.object(gate, "pr", return_value={"state": "open", "base": {"ref": base}}),
                patch.object(gate, "comment"),
                patch.object(gate, "run") as command,
                self.assertRaisesRegex(gate.ReleaseGateError, "must target master"),
            ):
                gate.checkout_release_branch(REPO, 166, branch, "0.12.0")
            command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
