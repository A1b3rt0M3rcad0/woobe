#!/bin/sh
set -e

# Runtime containers receive explicit dependency URLs from the deployment.
# Migrations are a separate job and are never inferred or executed here.
exec "$@"
