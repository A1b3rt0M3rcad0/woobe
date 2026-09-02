from __future__ import annotations

import argparse
import asyncio

from modules.identity.entrypoint import bootstrap_existing_owner_composer
from shared.presentation.http.request import Request


async def _bootstrap(owner_email: str) -> None:
    handler = bootstrap_existing_owner_composer()
    response = await handler(Request(body={"owner_email": owner_email}))
    owner_id = response.body["data"]["owner_user_id"]
    print(f"Woobe instance initialized with owner {owner_id}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize an existing Woobe Core database with an explicit Instance Owner"
    )
    parser.add_argument("--owner-email", required=True)
    args = parser.parse_args()
    asyncio.run(_bootstrap(args.owner_email))


if __name__ == "__main__":
    main()
