# Docker support files

`docker/` contains Docker build definitions that support repository validation or specialized build flows. It does not own the canonical Core deployment topology.

## Contents

`docker/tests/` contains backend test images used by `compose.test.yaml`, including the mocked and integration test runners.

The main backend runtime image is defined by the root `Dockerfile`. Frontend and ChatSurface images are owned by their product packages. The supported Core service topology is defined by root `compose.yaml`; Dockerfiles under this directory should not duplicate application architecture or Compose ownership.
