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
    expected = {
        line.strip()
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    if len(expected) != 178:
        print(f"Expected 178 reviewed failures, found {len(expected)}.", file=sys.stderr)
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
        f"known={len(expected)} actual={len(actual)} "
        f"unexpected={len(unexpected)} resolved={len(resolved)}"
    )

    for failure_hash in sorted(resolved):
        print(f"RESOLVED {failure_hash}")

    for failure_hash in sorted(unexpected):
        print(f"NEW {actual[failure_hash]} [{failure_hash}]", file=sys.stderr)

    return 1 if unexpected else 0


if __name__ == "__main__":
    raise SystemExit(main())
