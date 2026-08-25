#!/bin/sh
set -eu

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks is required; install it before running the public-history audit" >&2
  exit 2
fi

if [ ! -d .git ]; then
  echo "run this script from a full Git checkout" >&2
  exit 2
fi

git fetch --all --tags --prune

secret_report="gitleaks-public-history.json"
proprietary_report="proprietary-public-history.txt"

# Scan every reachable ref, not only the currently checked-out branch.
gitleaks git \
  --log-opts="--all" \
  --redact \
  --report-format json \
  --report-path "$secret_report" \
  .

# Known proprietary implementation paths removed from the Community HEAD must not
# remain reachable when the repository is made public. Historical migrations are
# intentionally excluded from this path check because they may be retained for
# database upgrade compatibility and require a separate publication decision.
: > "$proprietary_report"
for path in \
  src/editions/cloud \
  src/editions/enterprise \
  src/modules/billing \
  web/src/features/billing \
  tests/unit/billing \
  tests/integration/billing
 do
  git log --all --format= --name-only -- "$path" \
    | sed '/^[[:space:]]*$/d' \
    | sort -u \
    >> "$proprietary_report"
done

sort -u "$proprietary_report" -o "$proprietary_report"

if [ -s "$proprietary_report" ]; then
  printf '%s\n' "Historical proprietary paths are still reachable:" >&2
  cat "$proprietary_report" >&2
  printf '%s\n' "Sanitize/rewrite history or publish from a clean baseline before making the repository public." >&2
  exit 1
fi

printf '%s\n' "Secret history audit completed: $secret_report"
printf '%s\n' "Proprietary path history audit completed: $proprietary_report"
