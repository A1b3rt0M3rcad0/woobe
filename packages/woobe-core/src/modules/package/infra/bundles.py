from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import gzip
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile

from modules.package.application.validation import validate_document
from modules.package.domain.bundle import (
    MAX_ARCHIVE_BYTES,
    MAX_BUNDLE_BYTES,
    MAX_DESCRIPTOR_TOTAL,
    MAX_FILE_BYTES,
    MAX_FILES,
    PackageGraph,
    PathRegistry,
    inventory_digest,
    portable_path,
    resolve_graph,
    support_paths,
)
from modules.package.domain.errors import PackageError
from modules.package.domain.parsing import decode_document


class BoundedDecompression:
    """Bound tar headers and padding as well as the declared file payloads."""

    def __init__(self, stream, limit):
        self.stream = stream
        self.remaining = limit

    def read(self, size=-1):
        size = min(size, self.remaining + 1) if size >= 0 else self.remaining + 1
        block = self.stream.read(size)
        self.remaining -= len(block)
        if self.remaining < 0:
            raise PackageError(
                "PACKAGE_LIMIT_EXCEEDED", "Decompressed archive exceeds resource limit"
            )
        return block


@contextmanager
def confined_reader(root: Path, path: str):
    descriptors = []
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        parts = path.split("/")
        for part in parts[:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(fd)
        target = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(target, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise PackageError(
                    "PACKAGE_PATH_INVALID", "Only regular files are accepted", file=path
                )
            yield stream
    except OSError as exc:
        raise PackageError(
            "PACKAGE_PATH_INVALID",
            "File is unavailable or not confined to package root",
            file=path,
        ) from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


@dataclass
class Bundle:
    temporary: tempfile.TemporaryDirectory
    root: Path
    graph: PackageGraph
    inventory: list[dict]
    artifact_digest: str

    def close(self):
        self.temporary.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def lock(self):
        return {
            "format": "woobe-package",
            "schema_version": "1.0",
            "kind": "PackageLock",
            "algorithm": "sha256",
            "inventory": self.inventory,
            "artifact_digest": self.artifact_digest,
        }

    def archive(self, stream, *, include_lock=False):
        with gzip.GzipFile(
            fileobj=stream, mode="wb", mtime=0, filename=""
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|") as archive:
                for item in self.inventory:
                    info = tarfile.TarInfo(item["path"])
                    info.size, info.mode, info.mtime = item["size_bytes"], 0o600, 0
                    with (self.root / item["path"]).open("rb") as data:
                        archive.addfile(info, data)
                if include_lock:
                    data = (
                        json.dumps(
                            self.lock(),
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode()
                    info = tarfile.TarInfo("woobe.lock.json")
                    info.size, info.mode = len(data), 0o600
                    archive.addfile(info, io.BytesIO(data))


def snapshot_directory(source: Path, *, locked=False) -> Bundle:
    source = source.absolute()
    if source.name == "woobe.yaml":
        source = source.parent
    if source.is_symlink() or not source.is_dir():
        raise PackageError(
            "PACKAGE_PATH_INVALID",
            "Input must be a package directory or its woobe.yaml",
        )
    temporary = tempfile.TemporaryDirectory(prefix="woobe-package-")
    root = Path(temporary.name)
    inventory, seen, total = [], set(), 0
    registry = PathRegistry()

    def capture(path, limit=MAX_FILE_BYTES):
        nonlocal total
        path = portable_path(path)
        if path in {item["path"] for item in inventory}:
            return
        registry.register(path)
        if path.casefold() in seen or len(inventory) >= MAX_FILES:
            raise PackageError(
                "PACKAGE_PATH_INVALID",
                "File count limit or normalized path collision",
                file=path,
            )
        destination = root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest, size = sha256(), 0
        with confined_reader(source, path) as stream, destination.open("xb") as output:
            before = os.fstat(stream.fileno())
            if before.st_size > limit:
                raise PackageError(
                    "PACKAGE_LIMIT_EXCEEDED", "File exceeds 64 MiB", file=path
                )
            while block := stream.read(1 << 20):
                size += len(block)
                total += len(block)
                if size > limit or total > MAX_BUNDLE_BYTES:
                    raise PackageError(
                        "PACKAGE_LIMIT_EXCEEDED",
                        "Bundle resource limit exceeded",
                        file=path,
                    )
                digest.update(block)
                output.write(block)
            after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ) or size != before.st_size:
                raise PackageError(
                    "PACKAGE_FILE_CHANGED",
                    "File changed while creating snapshot",
                    file=path,
                )
        seen.add(path.casefold())
        inventory.append(
            {"path": path, "size_bytes": size, "sha256": digest.hexdigest()}
        )

    def descriptor(path):
        capture(path, limit=2 << 20)
        document = decode_document((root / path).read_bytes(), path)
        validate_document(document, path)
        return document

    try:
        manifest = descriptor("woobe.yaml")
        if manifest["kind"] != "Package":
            raise PackageError("PACKAGE_SCHEMA_INVALID", "woobe.yaml must be a Package")
        documents, descriptor_bytes = {}, (root / "woobe.yaml").stat().st_size
        for raw_path in manifest["spec"]["resources"]:
            path = portable_path(raw_path)
            if path in documents:
                raise PackageError(
                    "PACKAGE_REFERENCE_DUPLICATE",
                    "Resource path is duplicated",
                    file=path,
                )
            documents[path] = descriptor(path)
            descriptor_bytes += (root / path).stat().st_size
            if descriptor_bytes > MAX_DESCRIPTOR_TOTAL:
                raise PackageError(
                    "PACKAGE_LIMIT_EXCEEDED", "Descriptors exceed 16 MiB"
                )
            for support in support_paths(documents[path], path):
                capture(support)
        graph = resolve_graph(manifest, documents)
        inventory.sort(key=lambda item: item["path"])
        bundle = Bundle(temporary, root, graph, inventory, inventory_digest(inventory))
        lock_path = source / "woobe.lock.json"
        if lock_path.exists() or lock_path.is_symlink():
            with confined_reader(source, "woobe.lock.json") as stream:
                lock = decode_document(stream.read((2 << 20) + 1), "woobe.lock.json")
            validate_document(lock, "woobe.lock.json")
            if lock != bundle.lock():
                raise PackageError(
                    "PACKAGE_INTEGRITY_MISMATCH", "Lock differs from captured files"
                )
        elif locked:
            raise PackageError(
                "PACKAGE_LOCK_MISSING", "--locked requires woobe.lock.json"
            )
        return bundle
    except BaseException:
        temporary.cleanup()
        raise


def receive_archive(stream, *, locked=False) -> Bundle:
    with tempfile.TemporaryDirectory(prefix="woobe-package-upload-") as temp:
        root = Path(temp)
        archive_path = root / "transport.tar.gz"
        size = 0
        with archive_path.open("xb") as output:
            while block := stream.read(1 << 20):
                size += len(block)
                if size > MAX_ARCHIVE_BYTES:
                    raise PackageError(
                        "PACKAGE_LIMIT_EXCEEDED", "Compressed archive exceeds 128 MiB"
                    )
                output.write(block)
        content_root = root / "content"
        content_root.mkdir()
        try:
            with gzip.open(archive_path, mode="rb") as compressed:
                bounded = BoundedDecompression(
                    compressed, MAX_BUNDLE_BYTES + MAX_DESCRIPTOR_TOTAL
                )
                with tarfile.open(fileobj=bounded, mode="r|") as archive:
                    files, total = _extract_archive(archive, content_root)
                # Read through the gzip trailer even when tar stops at its end marker.
                while bounded.read(1 << 20):
                    pass
            bundle = snapshot_directory(content_root, locked=locked)
            declared = {item["path"].casefold() for item in bundle.inventory} | {
                "woobe.lock.json"
            }
            if files - declared:
                bundle.close()
                raise PackageError(
                    "PACKAGE_RESOURCE_INVALID", "Archive contains undeclared files"
                )
            return bundle
        except (tarfile.TarError, EOFError, OSError) as exc:
            raise PackageError(
                "PACKAGE_PARSE_INVALID", "Invalid or truncated archive"
            ) from exc


def _extract_archive(archive, content_root):
    files, total, entries = set(), 0, 0
    registry = PathRegistry()
    for entry in archive:
        entries += 1
        if entries > 2048:
            raise PackageError("PACKAGE_LIMIT_EXCEEDED", "Archive entry limit exceeded")
        if entry.isdir() and entry.name in {".", "./"}:
            continue
        path = portable_path(entry.name)
        registry.register(path, directory=entry.isdir())
        if entry.isdir():
            (content_root / path).mkdir(parents=True, exist_ok=True)
            continue
        if path.casefold() in files or len(files) >= MAX_FILES + 1:
            raise PackageError(
                "PACKAGE_PATH_INVALID",
                "Archive duplicate, case collision or file limit",
            )
        if not entry.isfile():
            raise PackageError(
                "PACKAGE_PATH_INVALID",
                "Archive only accepts regular file entries",
            )
        if entry.size > MAX_FILE_BYTES or entry.size < 0:
            raise PackageError(
                "PACKAGE_LIMIT_EXCEEDED",
                "Archive file exceeds resource limit",
            )
        total += entry.size
        if total > MAX_BUNDLE_BYTES:
            raise PackageError(
                "PACKAGE_LIMIT_EXCEEDED",
                "Uncompressed archive exceeds 512 MiB",
            )
        destination = content_root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = archive.extractfile(entry)
        with destination.open("xb") as output:
            while block := data.read(1 << 20):
                output.write(block)
        if destination.stat().st_size != entry.size:
            raise PackageError("PACKAGE_INTEGRITY_MISMATCH", "Truncated archive entry")
        files.add(path.casefold())
    return files, total
