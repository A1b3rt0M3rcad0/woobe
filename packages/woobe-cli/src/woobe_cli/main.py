from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class CliError(RuntimeError):
    pass


class WoobeClient:
    def __init__(self, *, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def request(
        self,
        method: str,
        path: str,
        *,
        query: list[str] | None = None,
        data: object | None = None,
        form: list[str] | None = None,
        files: list[str] | None = None,
    ) -> object:
        url = self._url(path, query or [])
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        body: bytes | None = None

        if files:
            body, content_type = _multipart_body(form or [], files)
            headers["Content-Type"] = content_type
        elif form:
            encoded = urlencode(dict(_pairs(form))).encode("utf-8")
            body = encoded
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif data is not None:
            body = json.dumps(data, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(
            url,
            data=body,
            headers=headers,
            method=method.upper(),
        )
        try:
            with urlopen(request) as response:
                raw = response.read()
        except HTTPError as exc:
            raw = exc.read()
            detail = raw.decode("utf-8", errors="replace")
            raise CliError(f"HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise CliError(f"Cannot reach Woobe: {exc.reason}") from exc

        if not raw:
            return None
        text = raw.decode("utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def _url(self, path: str, query: list[str]) -> str:
        normalized = path if path.startswith("/") else f"/{path}"
        pairs = _pairs(query)
        suffix = f"?{urlencode(pairs)}" if pairs else ""
        return f"{self.base_url}{normalized}{suffix}"


def _pairs(items: list[str]) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    for item in items:
        key, separator, value = item.partition("=")
        if not separator or not key:
            raise CliError(f"Expected KEY=VALUE, got: {item}")
        output.append((key, value))
    return output


def _json_input(value: str | None) -> object | None:
    if value is None:
        return None
    if value.startswith("@"):
        value = Path(value[1:]).read_text(encoding="utf-8")
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise CliError(f"Invalid JSON: {exc}") from exc


def _multipart_body(
    form: list[str],
    files: list[str],
) -> tuple[bytes, str]:
    boundary = f"woobe-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for key, value in _pairs(form):
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            ]
        )

    for spec in files:
        field, separator, file_name = spec.partition("=")
        if not separator or not field or not file_name:
            raise CliError(f"Expected FIELD=PATH, got: {spec}")
        path = Path(file_name)
        if not path.is_file():
            raise CliError(f"File not found: {path}")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{field}"; '
                    f'filename="{path.name}"\r\n'
                ).encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                path.read_bytes(),
                b"\r\n",
            ]
        )

    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _client(args: argparse.Namespace) -> WoobeClient:
    base_url = args.url or os.getenv("WOOBE_API_URL")
    api_key = args.api_key or os.getenv("WOOBE_API_KEY")
    if not base_url:
        raise CliError("Set --url or WOOBE_API_URL")
    if not api_key:
        raise CliError("Set --api-key or WOOBE_API_KEY")
    return WoobeClient(base_url=base_url, api_key=api_key)


def _print(value: object) -> None:
    if isinstance(value, str):
        print(value)
        return
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _add_auth(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--url", help="Woobe API base URL; defaults to WOOBE_API_URL")
    parser.add_argument(
        "--api-key",
        help="Control key; defaults to WOOBE_API_KEY",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="woobe")
    _add_auth(parser)
    commands = parser.add_subparsers(dest="command", required=True)

    request_parser = commands.add_parser(
        "request",
        help="Call any Woobe HTTP endpoint using the configured control key",
    )
    request_parser.add_argument("method")
    request_parser.add_argument("path")
    request_parser.add_argument("--query", action="append", default=[], metavar="KEY=VALUE")
    request_parser.add_argument("--data", help="JSON string or @path/to/file.json")
    request_parser.add_argument("--form", action="append", default=[], metavar="KEY=VALUE")
    request_parser.add_argument("--file", action="append", default=[], metavar="FIELD=PATH")

    key_parser = commands.add_parser("control-key")
    key_commands = key_parser.add_subparsers(dest="key_command", required=True)

    key_list = key_commands.add_parser("list")
    key_list.add_argument("--workspace", required=True)

    key_create = key_commands.add_parser("create")
    key_create.add_argument("--workspace", required=True)
    key_create.add_argument("--name", required=True)
    key_create.add_argument("--description")
    key_create.add_argument("--permissions", default="")
    key_create.add_argument(
        "--grants",
        default="[]",
        help="JSON array or @file with [{project_id, permissions}]",
    )
    key_create.add_argument("--expires-at")

    key_update = key_commands.add_parser("update")
    key_update.add_argument("--workspace", required=True)
    key_update.add_argument("--key-id", required=True)
    key_update.add_argument("--name")
    key_update.add_argument("--description")
    key_update.add_argument("--permissions")
    key_update.add_argument("--grants")
    key_update.add_argument("--expires-at")

    key_revoke = key_commands.add_parser("revoke")
    key_revoke.add_argument("--workspace", required=True)
    key_revoke.add_argument("--key-id", required=True)

    key_rotate = key_commands.add_parser("rotate")
    key_rotate.add_argument("--workspace", required=True)
    key_rotate.add_argument("--key-id", required=True)
    key_rotate.add_argument("--name")
    key_rotate.add_argument("--expires-at")

    return parser


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def run(args: argparse.Namespace) -> object:
    client = _client(args)

    if args.command == "request":
        return client.request(
            args.method,
            args.path,
            query=args.query,
            data=_json_input(args.data),
            form=args.form,
            files=args.file,
        )

    if args.command == "control-key":
        base = f"/core/workspaces/{args.workspace}/control-keys"
        if args.key_command == "list":
            return client.request("GET", base)
        if args.key_command == "create":
            payload = {
                "name": args.name,
                "description": args.description,
                "permissions": _csv(args.permissions),
                "project_grants": _json_input(args.grants) or [],
            }
            if args.expires_at:
                payload["expires_at"] = args.expires_at
            return client.request("POST", base, data=payload)
        if args.key_command == "update":
            payload: dict[str, object] = {}
            if args.name is not None:
                payload["name"] = args.name
            if args.description is not None:
                payload["description"] = args.description
            if args.permissions is not None:
                payload["permissions"] = _csv(args.permissions)
            if args.grants is not None:
                payload["project_grants"] = _json_input(args.grants)
            if args.expires_at is not None:
                payload["expires_at"] = args.expires_at or None
            return client.request(
                "PATCH",
                f"{base}/{args.key_id}",
                data=payload,
            )
        if args.key_command == "revoke":
            return client.request("POST", f"{base}/{args.key_id}/revoke", data={})
        if args.key_command == "rotate":
            payload = {}
            if args.name is not None:
                payload["name"] = args.name
            if args.expires_at is not None:
                payload["expires_at"] = args.expires_at or None
            return client.request(
                "POST",
                f"{base}/{args.key_id}/rotate",
                data=payload,
            )

    raise CliError("Unsupported command")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        _print(run(args))
    except (CliError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
