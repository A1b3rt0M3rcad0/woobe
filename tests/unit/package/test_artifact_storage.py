from hashlib import sha256
import io
from uuid import uuid4

import pytest

from modules.package.domain.errors import PackageError
from modules.package.infra.artifact_storage import LocalPackageArtifactStorage


def test_local_artifact_is_durable_private_and_never_replaced(tmp_path):
    storage = LocalPackageArtifactStorage(tmp_path)
    key = f"projects/{uuid4()}/uploads/{uuid4()}.tar.gz"
    receipt = storage.put(key, io.BytesIO(b"complete-artifact"))
    assert receipt == {
        "size_bytes": 17,
        "transport_digest": sha256(b"complete-artifact").hexdigest(),
    }
    with pytest.raises(FileExistsError):
        storage.put(key, io.BytesIO(b"replacement"))
    with LocalPackageArtifactStorage(tmp_path).open(key) as stream:
        assert stream.read() == b"complete-artifact"
    assert (storage.root / key).stat().st_mode & 0o777 == 0o600
    assert not list(storage.root.rglob("*.tmp"))


def test_artifact_storage_cannot_follow_symlinked_project_directories(tmp_path):
    storage = LocalPackageArtifactStorage(tmp_path)
    (storage.root / "projects").mkdir()
    project = uuid4()
    outside = tmp_path / "outside"
    outside.mkdir()
    (storage.root / "projects" / str(project)).symlink_to(outside)
    with pytest.raises(OSError):
        storage.put(f"projects/{project}/uploads/{uuid4()}.tar.gz", io.BytesIO(b"data"))
    assert not list(outside.iterdir())


@pytest.mark.parametrize(
    "key",
    [
        "../escape",
        "/absolute",
        "projects/no-project/uploads/no-upload.tar.gz",
        "projects/../../escape",
    ],
)
def test_artifact_storage_only_accepts_owned_keys(tmp_path, key):
    with pytest.raises(PackageError):
        LocalPackageArtifactStorage(tmp_path).put(key, io.BytesIO(b"data"))


def test_artifact_storage_cleans_partial_oversized_transfers(tmp_path, monkeypatch):
    import modules.package.infra.artifact_storage as module

    monkeypatch.setattr(module, "MAX_ARCHIVE_BYTES", 3)
    storage = LocalPackageArtifactStorage(tmp_path)
    key = f"projects/{uuid4()}/uploads/{uuid4()}.tar.gz"
    with pytest.raises(PackageError):
        storage.put(key, io.BytesIO(b"exceeds"))
    assert not (storage.root / key).exists()
    assert not list(storage.root.rglob("*.tmp"))
