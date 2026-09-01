"""shared limiter persistence."""

from modules.core.infra.database.coordination_schema import (
    downgrade as apply_downgrade,
)
from modules.core.infra.database.coordination_schema import upgrade as apply_upgrade

revision = str(30).zfill(4)
down_revision = str(29).zfill(4)
branch_labels = None
depends_on = None


def upgrade() -> None:
    apply_upgrade()


def downgrade() -> None:
    apply_downgrade()
