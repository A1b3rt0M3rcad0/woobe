.PHONY: build test check package version
build:
	python3 scripts/version.py
	go build -trimpath -ldflags="-X github.com/A1b3rt0M3rcad0/woobe-cli/internal/cli.Version=$$(python3 scripts/version.py) -X github.com/A1b3rt0M3rcad0/woobe-cli/internal/cli.Commit=$$(git rev-parse HEAD)" -o bin/woobe ./cmd/woobe
test:
	go test -race ./...
check:
	node --test scripts/tests/skill-installer.test.cjs
	python3 scripts/version.py
	python3 -m unittest discover -s scripts/tests
	python3 scripts/completeness.py
	test -z "$$(gofmt -l cmd internal packages)"
	go mod verify
	go vet ./...
	go test -race ./...
package:
	bash scripts/package.sh
	python3 scripts/verify_artifacts.py
version:
	python3 scripts/version.py
