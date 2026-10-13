from hashlib import sha256
from importlib.resources import files
from types import SimpleNamespace

import pytest

from modules.package.infra import native_inspector


@pytest.mark.asyncio
async def test_capabilities_catalog_digest_ignores_windows_checkout_line_endings(tmp_path, monkeypatch):
    catalog = files("modules.package.domain.schemas").joinpath("catalog.json").read_bytes().replace(b"\r\n", b"\n")
    expected = sha256(catalog).hexdigest()
    catalog_v2 = files("modules.package.domain.schemas").joinpath("catalog-v2.json").read_bytes().replace(b"\r\n", b"\n")
    (tmp_path / "catalog-v2.json").write_bytes(catalog_v2.replace(b"\n", b"\r\n"))
    gateway = native_inspector.NativePackageInspectorGateway(
        None, SimpleNamespace(package_capabilities=lambda: {})
    )
    monkeypatch.setattr(native_inspector, "files", lambda _: tmp_path)
    monkeypatch.setattr(native_inspector, "portable_definition_capabilities", lambda: {})
    for contents in (catalog, catalog.replace(b"\n", b"\r\n")):
        (tmp_path / "catalog.json").write_bytes(contents)
        capabilities = await gateway.capabilities()
        assert capabilities["schema_catalog_sha256"] == expected
        assert capabilities["supported_package_schemas"] == {"1.0": expected, "2.0": sha256(catalog_v2).hexdigest()}
        assert capabilities["structural_installation"] is True

    # Keep real schema changes incompatible; do not hash only the version marker.
    changed = catalog.replace(b'"type": "object"', b'"type": "array"', 1)
    assert changed != catalog
    (tmp_path / "catalog.json").write_bytes(changed)
    assert (await gateway.capabilities())["schema_catalog_sha256"] != expected
