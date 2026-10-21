# Public Release Checklist

Use this checklist together with [../RELEASING.md](../RELEASING.md).

## Version and history

- [ ] `pyproject.toml` contains the intended PEP 440 version.
- [ ] Tag name will be exactly `v<VERSION>`.
- [ ] Release branch was created from the intended `master` commit.
- [ ] `CHANGELOG.md` contains the dated release section.
- [ ] Contributor accounting covers the correct PR/commit range.

## API and compatibility

- [ ] Public API changes are documented.
- [ ] Breaking changes include migration guidance.
- [ ] Runtime protocol compatibility is explicitly reviewed.
- [ ] Minimum Python/dependency changes are documented.
- [ ] Examples still match the supported API.

## Validation

- [ ] `ruff check .`
- [ ] `pytest`
- [ ] Supported Python versions pass CI.
- [ ] `python -m build`
- [ ] `twine check dist/*`
- [ ] Wheel and sdist contents inspected.
- [ ] Clean-install smoke test completed.

## Security and supply chain

- [ ] No Runtime Keys, credentials, local config or private artifacts are packaged.
- [ ] New dependencies have known provenance.
- [ ] Security-impacting dependency changes were reviewed.
- [ ] GitHub Actions use intentional, reviewed permissions.

## Licensing and brand

- [ ] `LICENSE.md` remains the canonical MIT license.
- [ ] Package metadata declares MIT.
- [ ] Required third-party notices are present.
- [ ] Woobe trademarks are not represented as part of the MIT grant.
- [ ] Release wording does not imply that the Woobe server is MIT.

## Publication

- [ ] PyPI Trusted Publisher is configured for `.github/workflows/release.yml`.
- [ ] GitHub `pypi` environment is configured.
- [ ] Release PR is merged to `master`.
- [ ] `master` checks are green.
- [ ] Annotated release tag is pushed only after merge.
- [ ] PyPI package, GitHub Release and attached artifacts are verified after publication.
