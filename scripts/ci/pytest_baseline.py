from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPORT_PATH = Path("pytest-report.xml")
BASELINE_PATH = Path("tests/ci/known_pytest_failures.txt")


def _load_expected_failures() -> set[str]:
    if not BASELINE_PATH.is_file():
        raise RuntimeError(f"Pytest failure baseline not found: {BASELINE_PATH}")

    return {
        line.strip()
        for line in BASELINE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _load_actual_failures() -> set[str]:
    if not REPORT_PATH.is_file():
        raise RuntimeError(f"Pytest did not produce JUnit report: {REPORT_PATH}")

    root = ET.parse(REPORT_PATH).getroot()
    failures: set[str] = set()
    for testcase in root.iter("testcase"):
        failure = testcase.find("failure")
        error = testcase.find("error")
        if failure is None and error is None:
            continue

        classname = testcase.get("classname") or "<unknown-class>"
        name = testcase.get("name") or "<unknown-test>"
        failures.add(f"{classname}::{name}")

    return failures


def main() -> int:
    expected = _load_expected_failures()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            f"--junitxml={REPORT_PATH}",
        ],
        check=False,
    )

    # Pytest exit code 1 means tests failed and is handled by the baseline.
    # Collection, usage, internal, interrupted, or no-tests errors remain fatal.
    if result.returncode not in (0, 1):
        print(
            f"Pytest terminated with unsupported exit code {result.returncode}.",
            file=sys.stderr,
        )
        return result.returncode or 2

    actual = _load_actual_failures()
    unexpected = actual - expected
    resolved = expected - actual

    print(
        "Pytest baseline summary: "
        f"actual_failures={len(actual)}, "
        f"known_failures={len(expected)}, "
        f"unexpected_failures={len(unexpected)}, "
        f"resolved_known_failures={len(resolved)}"
    )

    if resolved:
        print("Known failures that are now passing and can be removed from the baseline:")
        for test_id in sorted(resolved):
            print(f"  RESOLVED {test_id}")

    if unexpected:
        print("New failures outside the approved baseline:", file=sys.stderr)
        for test_id in sorted(unexpected):
            print(f"  NEW {test_id}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
