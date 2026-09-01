from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import signal
from pathlib import Path


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            chunk = await reader.read(1024 * 1024)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    except (ConnectionError, BrokenPipeError, asyncio.CancelledError):
        pass
    finally:
        with contextlib.suppress(Exception):
            writer.close()
            await writer.wait_closed()


async def _handle_client(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    *,
    upstream: str,
) -> None:
    try:
        upstream_reader, upstream_writer = await asyncio.open_unix_connection(upstream)
    except Exception:
        client_writer.close()
        with contextlib.suppress(Exception):
            await client_writer.wait_closed()
        return

    left = asyncio.create_task(_pipe(client_reader, upstream_writer))
    right = asyncio.create_task(_pipe(upstream_reader, client_writer))
    done, pending = await asyncio.wait(
        {left, right},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    for task in done | pending:
        with contextlib.suppress(Exception, asyncio.CancelledError):
            await task


async def _main(listen: str, upstream: str) -> None:
    listen_path = Path(listen)
    listen_path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(FileNotFoundError):
        listen_path.unlink()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signame in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(signame, stop.set)

    server = await asyncio.start_unix_server(
        lambda reader, writer: _handle_client(
            reader,
            writer,
            upstream=upstream,
        ),
        path=str(listen_path),
    )
    os.chmod(listen_path, 0o600)

    try:
        async with server:
            await stop.wait()
    finally:
        server.close()
        await server.wait_closed()
        with contextlib.suppress(FileNotFoundError):
            listen_path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Expose the Docker Unix socket through a user-owned Unix socket.",
    )
    parser.add_argument("--listen", required=True)
    parser.add_argument("--upstream", default="/var/run/docker.sock")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(_main(args.listen, args.upstream))
