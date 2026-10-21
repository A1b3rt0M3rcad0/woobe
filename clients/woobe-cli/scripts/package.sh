#!/usr/bin/env bash
set -euo pipefail
canonical_version="$(python3 scripts/version.py)"
version="${1:-$canonical_version}"
version="${version#v}"
python3 scripts/version.py --validate "$version" >/dev/null
with_npm="${2:-}"
if [[ -n "$with_npm" && "$with_npm" != --with-npm ]]; then
  echo 'usage: package.sh [VERSION] [--with-npm]' >&2
  exit 2
fi
mkdir -p dist
rm -rf dist/npm
export TZ=UTC
task_epoch="$(git show -s --format=%ct HEAD)"
python3 scripts/third_party_notices.py dist/THIRD_PARTY_NOTICES.txt
task_schema="$(mktemp)"
task_resources="$(mktemp)"
trap 'rm -f "$task_schema" "$task_resources"; if [[ -n "${task_dir:-}" ]]; then rm -rf "$task_dir"; fi' EXIT
go run ./cmd/woobe schema --command "manifest validate" --kind document > "$task_schema"
go run ./cmd/woobe schema --command "manifest validate" --kind document --manifest-version 2 > "$task_resources"
for target_os in linux darwin windows; do
  for target_arch in amd64 arm64; do
    task_dir="$(mktemp -d)"
    executable=woobe
    if [[ "$target_os" == windows ]]; then executable=woobe.exe; fi
    CGO_ENABLED=0 GOOS="$target_os" GOARCH="$target_arch" go build -trimpath -ldflags="-s -w -X github.com/A1b3rt0M3rcad0/woobe-cli/internal/cli.Version=$version -X github.com/A1b3rt0M3rcad0/woobe-cli/internal/cli.Commit=$(git rev-parse HEAD)" -o "$task_dir/$executable" ./cmd/woobe
    if [[ "$with_npm" == --with-npm ]]; then
      mkdir -p "dist/npm/vendor/$target_os-$target_arch"
      cp "$task_dir/$executable" "dist/npm/vendor/$target_os-$target_arch/$executable"
      chmod 755 "dist/npm/vendor/$target_os-$target_arch/$executable"
    fi
    cp README.md "$task_dir/README.md"
    cp dist/THIRD_PARTY_NOTICES.txt "$task_dir/THIRD_PARTY_NOTICES.txt"
 cp docs/USAGE.md "$task_dir/USAGE.md"
 python3 - "$task_schema" "$task_dir/manifest.schema.json" <<'PYSCHEMA'
import json,sys
with open(sys.argv[1]) as f: schema=json.load(f)["data"]
with open(sys.argv[2],"w") as f: json.dump(schema,f,indent=2);f.write("\n")
PYSCHEMA
    python3 - "$task_resources" "$task_dir/resources.schema.json" <<'PYRESOURCE'
import json,sys
with open(sys.argv[1]) as f: schema=json.load(f)["data"]
with open(sys.argv[2],"w") as f: json.dump(schema,f,indent=2);f.write("\n")
PYRESOURCE
    archive="woobe_${version}_${target_os}_${target_arch}"
    # A retry must produce the same bytes, including archive metadata.
    find "$task_dir" -type f -exec touch -d "@$task_epoch" {} +
    if [[ "$target_os" == windows ]]; then
      task_archive="$(pwd)/dist/$archive.zip"
      rm -f "$task_archive"
      (cd "$task_dir" && zip -X -q "$task_archive" "$executable" README.md USAGE.md manifest.schema.json resources.schema.json THIRD_PARTY_NOTICES.txt)
    else
      tar --mtime="@$task_epoch" --owner=0 --group=0 --numeric-owner -cf - -C "$task_dir" "$executable" README.md USAGE.md manifest.schema.json resources.schema.json THIRD_PARTY_NOTICES.txt | gzip -n > "dist/$archive.tar.gz"
    fi
    rm -rf "$task_dir"
  done
done
if [[ "$with_npm" == --with-npm ]]; then
  python3 scripts/package_npm.py "$version"
  python3 scripts/package_skill.py "$version" --commit "$(git rev-parse HEAD)"
  (cd dist && sha256sum "woobe_${version}_"*.tar.gz "woobe_${version}_"*.zip "woobe-cli-${version}.tgz" "woobe-cli-skill-${version}.tgz" > SHA256SUMS)
else
  (cd dist && sha256sum "woobe_${version}_"*.tar.gz "woobe_${version}_"*.zip > SHA256SUMS)
fi
python3 scripts/artifact_manifest.py "$version" "$(git rev-parse HEAD)" "$(go version)" "$with_npm"
