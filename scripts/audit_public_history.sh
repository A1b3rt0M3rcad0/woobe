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
gitleaks git --redact --report-format json --report-path gitleaks-public-history.json .
printf '%s\n' "Secret history audit completed: gitleaks-public-history.json"
