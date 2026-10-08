import io
import os

import pytest

from modules.agent.infra.storage.local_file_storage import LocalFileStorage
from modules.agent.infra.storage.s3_file_storage import S3FileStorage


@pytest.mark.asyncio
async def test_local_export_read_is_bounded_and_never_follows_links_or_special_files(
    tmp_path,
):
    storage = LocalFileStorage(tmp_path)
    (tmp_path / "document.txt").write_bytes(b"portable")
    assert (
        await storage.read_document_bounded("document.txt", max_bytes=8) == b"portable"
    )
    with pytest.raises(ValueError):
        await storage.read_document_bounded("document.txt", max_bytes=7)
    (tmp_path / "linked.txt").symlink_to(tmp_path / "document.txt")
    with pytest.raises(OSError):
        await storage.read_document_bounded("linked.txt", max_bytes=8)
    os.link(tmp_path / "document.txt", tmp_path / "hardlink.txt")
    with pytest.raises(ValueError):
        await storage.read_document_bounded("hardlink.txt", max_bytes=8)
    os.mkfifo(tmp_path / "pipe.txt")
    with pytest.raises(ValueError):
        await storage.read_document_bounded("pipe.txt", max_bytes=8)
    with pytest.raises(ValueError):
        await storage.read_document_bounded("../document.txt", max_bytes=8)


@pytest.mark.asyncio
@pytest.mark.parametrize("reported_size", [None, 100])
async def test_s3_export_read_bounds_body_and_closes_it_on_failure(reported_size):
    stream = io.BytesIO(b"too large")

    class Client:
        def get_object(self, **kwargs):
            assert kwargs == {"Bucket": "test", "Key": "document"}
            response = {"Body": stream}
            if reported_size is not None:
                response["ContentLength"] = reported_size
            return response

    storage = object.__new__(S3FileStorage)
    storage._client, storage._bucket = Client(), "test"
    with pytest.raises(ValueError):
        await storage.read_document_bounded("document", max_bytes=4)
    assert stream.closed
