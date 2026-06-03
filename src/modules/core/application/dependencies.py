from uuid import UUID


async def get_current_user_id() -> UUID:
    return UUID("00000000-0000-0000-0000-000000000001")
