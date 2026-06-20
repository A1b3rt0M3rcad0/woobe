"""shared limiter persistence."""

from shared.security.limiter_schema import downgrade, upgrade

revision = str(30).zfill(4)
down_revision = str(29).zfill(4)
branch_labels = None
depends_on = None
