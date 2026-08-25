from __future__ import annotations

import argparse
import asyncio

from modules.identity.application.instance_service import InstanceService
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.security.access_tokens import AccessTokenCodec


async def _bootstrap(owner_email: str) -> None:
    settings = Settings(service_role="api")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    codec = AccessTokenCodec(
        signing_key=settings.secret_key,
        issuer=settings.auth_issuer,
        audience=settings.auth_audience,
        ttl_seconds=settings.access_token_ttl_seconds,
        leeway_seconds=settings.auth_clock_skew_seconds,
    )
    try:
        owner_id = await InstanceService(
            session_factory,
            codec,
            settings,
        ).bootstrap_existing_owner(owner_email=owner_email)
    finally:
        await engine.dispose()
    print(f"Woobe instance initialized with owner {owner_id}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize an existing Woobe Community database with an explicit Instance Owner"
    )
    parser.add_argument("--owner-email", required=True)
    args = parser.parse_args()
    asyncio.run(_bootstrap(args.owner_email))


if __name__ == "__main__":
    main()
