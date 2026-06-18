# CI and branch protection

This branch establishes required quality gates for pull requests targeting `development-mvp` and the final promotion to `development`.

Required checks:

- Backend / quality
- Frontend / build-and-test
- Migrations / schema
- Containers / build
- Containers / smoke

Direct pushes, force pushes, branch deletion, unresolved conversations, and merges with failing checks must be blocked.
