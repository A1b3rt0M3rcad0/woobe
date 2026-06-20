"""shared limiter persistence."""

from shared.security.limiter_schema import downgrade, upgrade

revision = str(28).zfill(4)
down_revision = str(27).zfill(4)
branch_labels = None
depends_on = None
