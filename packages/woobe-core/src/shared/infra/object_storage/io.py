import asyncio


async def run_blocking(function, *args, on_cancel=None, **kwargs):
    """Wait for owned OS work before cancellation closes/reuses its descriptors."""
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            if task.cancelled():
                raise
            cancelled = True
    if cancelled:
        if on_cancel is not None:
            await run_blocking(on_cancel, result)
        raise asyncio.CancelledError
    return result

