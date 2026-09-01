"""Persist meaningful titles for Network Sessions.

Revision ID: 0048
Revises: 0047
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0048"
down_revision: str | None = "0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_AUTOMATIC_TITLE_PATTERN = (
    r"^(new([[:space:]]+(network|draft|staging|production))?[[:space:]]+session"
    r"|draft[[:space:]]+·[[:space:]]+"
    r"|staging[[:space:]]+·[[:space:]]+"
    r"|production[[:space:]]+·[[:space:]]+)"
)


def upgrade() -> None:
    op.execute(
        f"""
        WITH first_messages AS (
            SELECT DISTINCT ON (network_session_id)
                network_session_id,
                content
            FROM network.network_messages
            WHERE role = 'user' AND btrim(content) <> ''
            ORDER BY network_session_id, created_at ASC, id ASC
        )
        UPDATE network.network_sessions AS network_session
        SET
            title = left(
                regexp_replace(
                    btrim(first_message.content),
                    '[[:space:]]+',
                    ' ',
                    'g'
                ),
                72
            ),
            updated_at = now()
        FROM first_messages AS first_message
        WHERE first_message.network_session_id = network_session.id
          AND network_session.title ~* '{_AUTOMATIC_TITLE_PATTERN}'
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION network.rename_automatic_network_session()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.role <> 'user' OR btrim(NEW.content) = '' THEN
                RETURN NEW;
            END IF;

            UPDATE network.network_sessions AS network_session
            SET
                title = left(
                    regexp_replace(
                        btrim(NEW.content),
                        '[[:space:]]+',
                        ' ',
                        'g'
                    ),
                    72
                ),
                updated_at = now()
            WHERE network_session.id = NEW.network_session_id
              AND network_session.title ~* '{_AUTOMATIC_TITLE_PATTERN}'
              AND NOT EXISTS (
                  SELECT 1
                  FROM network.network_messages AS previous_message
                  WHERE previous_message.network_session_id = NEW.network_session_id
                    AND previous_message.role = 'user'
                    AND previous_message.id <> NEW.id
              );

            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_network_session_title_from_first_message
        AFTER INSERT ON network.network_messages
        FOR EACH ROW
        EXECUTE FUNCTION network.rename_automatic_network_session()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_network_session_title_from_first_message "
        "ON network.network_messages"
    )
    op.execute("DROP FUNCTION IF EXISTS network.rename_automatic_network_session()")
