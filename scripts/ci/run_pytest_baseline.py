from __future__ import annotations

import hashlib
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPORT = Path("pytest-report.xml")
BASELINE = Path("tests/ci/known_pytest_failure_hashes.txt")


def test_hash(test_id: str) -> str:
    return hashlib.sha256(test_id.encode()).hexdigest()


def main() -> int:
    baseline_lines = [
        line.strip()
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    expected = set(baseline_lines)
    if not expected:
        print("The reviewed pytest failure baseline is empty.", file=sys.stderr)
        return 2
    if len(expected) != len(baseline_lines):
        print("The reviewed pytest failure baseline contains duplicates.", file=sys.stderr)
        return 2

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", f"--junitxml={REPORT}"],
        check=False,
    )
    if result.returncode not in (0, 1):
        return result.returncode or 2

    actual: dict[str, str] = {}
    root = ET.parse(REPORT).getroot()
    for case in root.iter("testcase"):
        if case.find("failure") is None and case.find("error") is None:
            continue
        test_id = f"{case.get('classname', '<unknown>')}::{case.get('name', '<unknown>')}"
        actual[test_hash(test_id)] = test_id

    unexpected = set(actual) - expected
    resolved = expected - set(actual)
    print(
        "Pytest baseline: "
        f"reviewed={len(expected)} actual={len(actual)} "
        f"unexpected={len(unexpected)} stale={len(resolved)}"
    )

    for failure_hash in sorted(resolved):
        print(f"STALE {failure_hash}", file=sys.stderr)

    for failure_hash in sorted(unexpected):
        print(f"NEW {actual[failure_hash]} [{failure_hash}]", file=sys.stderr)

    if resolved:
        print(
            "Remove resolved failures from the reviewed baseline in the same PR; "
            "the allowlist may only shrink.",
            file=sys.stderr,
        )
    return 1 if unexpected or resolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
