from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "release_dispatch", ROOT / "scripts/release/dispatch_and_wait.py"
)
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)


class ReleaseDispatchTests(unittest.TestCase):
    def test_parse_inputs_requires_key_value_pairs(self):
        self.assertEqual(
            dispatch.parse_inputs(["version=0.12.0", "ref=abc"]),
            ["-f", "version=0.12.0", "-f", "ref=abc"],
        )
        with self.assertRaisesRegex(dispatch.WorkflowDispatchError, "expected key=value"):
            dispatch.parse_inputs(["invalid"])

    def test_find_run_matches_exact_title_and_dispatch_window(self):
        now = datetime(2026, 9, 25, 19, 0, tzinfo=timezone.utc)
        items = [
            {
                "id": 1,
                "display_title": "Release candidate 0.12.0 @ abc / 10",
                "created_at": "2026-09-25T18:59:59Z",
            },
            {
                "id": 2,
                "display_title": "Release candidate 0.12.0 @ abc / 11",
                "created_at": "2026-09-25T19:00:01Z",
            },
            {
                "id": 3,
                "display_title": "Release candidate 0.12.0 @ abc / 10",
                "created_at": "2026-09-25T19:00:02Z",
            },
        ]
        with patch.object(dispatch, "list_runs", return_value=items):
            result = dispatch.find_run(
                "owner/woobe",
                "release-candidate.yml",
                "Release candidate 0.12.0 @ abc / 10",
                now,
            )
        self.assertEqual(result["id"], 3)

    def test_main_dispatches_and_propagates_child_failure(self):
        args = SimpleNamespace(
            repo="owner/woobe",
            workflow="release.yml",
            ref="master",
            expected_title="Publish Woobe 0.12.0 @ abc / 10",
            input=["version=0.12.0"],
            timeout_seconds=30,
            poll_seconds=0,
            github_output=None,
            output_prefix="publication",
        )
        child = {
            "id": 99,
            "html_url": "https://github.com/owner/woobe/actions/runs/99",
        }
        with (
            patch.object(dispatch, "parse_args", return_value=args),
            patch.object(dispatch, "run") as command,
            patch.object(dispatch, "find_run", return_value=child),
            patch.object(
                dispatch,
                "gh_json",
                return_value={"status": "completed", "conclusion": "failure"},
            ),
            self.assertRaisesRegex(dispatch.WorkflowDispatchError, "completed with failure"),
        ):
            dispatch.main()

        dispatched = command.call_args_list[0].args[0]
        self.assertEqual(dispatched[:5], ["gh", "workflow", "run", "release.yml", "--repo"])
        self.assertIn("version=0.12.0", dispatched)

    def test_main_returns_only_after_exact_child_success(self):
        args = SimpleNamespace(
            repo="owner/woobe",
            workflow="release-candidate.yml",
            ref="master",
            expected_title="Release candidate 0.12.0 @ abc / 10",
            input=["ref=abc"],
            timeout_seconds=30,
            poll_seconds=0,
            github_output=None,
            output_prefix="candidate",
        )
        child = {
            "id": 100,
            "html_url": "https://github.com/owner/woobe/actions/runs/100",
        }
        with (
            patch.object(dispatch, "parse_args", return_value=args),
            patch.object(dispatch, "run"),
            patch.object(dispatch, "find_run", return_value=child),
            patch.object(
                dispatch,
                "gh_json",
                side_effect=[
                    {"status": "in_progress", "conclusion": None},
                    {"status": "completed", "conclusion": "success"},
                ],
            ),
            patch.object(dispatch.time, "sleep"),
        ):
            self.assertEqual(dispatch.main(), 0)


if __name__ == "__main__":
    unittest.main()
