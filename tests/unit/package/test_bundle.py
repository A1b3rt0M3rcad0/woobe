from hashlib import sha256
import io
import json
import tarfile

import pytest

from modules.package.domain.bundle import inventory_digest, portable_path, resolve_graph
from modules.package.domain.bundle import PathRegistry, validate_network_structure
from modules.package.domain.errors import PackageError
from modules.package.infra.bundles import receive_archive, snapshot_directory


def package(tmp_path):
    manifest = {
        "format": "woobe-package",
        "schema_version": "1.0",
        "kind": "Package",
        "metadata": {"name": "support", "version": "1.0.0"},
        "spec": {
            "entrypoint": {"kind": "Agent", "ref": "support"},
            "resources": ["agent.yaml", "model.yaml"],
            "requires": {
                "credentials": [{"ref": "primary-key", "provider": "openai_compatible"}]
            },
        },
    }
    model = {
        "format": "woobe-package",
        "schema_version": "1.0",
        "kind": "Model",
        "metadata": {"key": "primary", "name": "Primary"},
        "spec": {
            "provider": "openai_compatible",
            "model": "fake",
            "credential": {"ref": "primary-key"},
        },
    }
    agent = {
        "format": "woobe-package",
        "schema_version": "1.0",
        "kind": "Agent",
        "metadata": {"key": "support", "name": "Support"},
        "spec": {
            "model": {"primary": {"ref": "primary"}},
            "legacy_system_prompt": "Answer",
        },
    }
    for name, value in [
        ("woobe.yaml", manifest),
        ("agent.yaml", agent),
        ("model.yaml", model),
    ]:
        (tmp_path / name).write_text(json.dumps(value))
    return manifest, agent, model


def test_only_declared_files_are_snapshotted_and_bytes_are_immutable(tmp_path):
    package(tmp_path)
    (tmp_path / "incidental-secret.txt").write_text("never bundled")
    with snapshot_directory(tmp_path) as bundle:
        assert {item["path"] for item in bundle.inventory} == {
            "woobe.yaml",
            "agent.yaml",
            "model.yaml",
        }
        captured = (bundle.root / "agent.yaml").read_bytes()
        (tmp_path / "agent.yaml").write_text("changed")
        assert (bundle.root / "agent.yaml").read_bytes() == captured
        archive = io.BytesIO()
        bundle.archive(archive, include_lock=True)
        with receive_archive(io.BytesIO(archive.getvalue()), locked=True) as received:
            assert received.artifact_digest == bundle.artifact_digest
            assert received.graph.components == bundle.graph.components


def test_lock_is_required_and_never_rewritten(tmp_path):
    package(tmp_path)
    with pytest.raises(PackageError, match="requires"):
        snapshot_directory(tmp_path, locked=True)
    with snapshot_directory(tmp_path) as bundle:
        lock = bundle.lock()
    (tmp_path / "woobe.lock.json").write_text(json.dumps(lock))
    with snapshot_directory(tmp_path, locked=True):
        pass
    (tmp_path / "agent.yaml").write_text((tmp_path / "agent.yaml").read_text() + "\n")
    before = (tmp_path / "woobe.lock.json").read_bytes()
    with pytest.raises(PackageError) as caught:
        snapshot_directory(tmp_path, locked=True)
    assert caught.value.code == "PACKAGE_INTEGRITY_MISMATCH"
    assert (tmp_path / "woobe.lock.json").read_bytes() == before


@pytest.mark.parametrize(
    "path",
    [
        "../escape",
        "/absolute",
        "C:/drive",
        "a\\b",
        "CON.txt",
        "a/NUL",
        "a:stream",
        ".git/config",
        "trailing.",
        "trailing ",
    ],
)
def test_nonportable_paths_are_rejected(path):
    with pytest.raises(PackageError):
        portable_path(path)


def test_descriptor_relative_path_can_use_parent_without_escaping_root():
    assert (
        portable_path("../documents/policy.md", descriptor="knowledge/main.yaml")
        == "documents/policy.md"
    )
    with pytest.raises(PackageError):
        portable_path("../../escape", descriptor="knowledge/main.yaml")


def test_symlink_cannot_become_a_descriptor(tmp_path):
    package(tmp_path)
    (tmp_path / "agent.yaml").unlink()
    (tmp_path / "agent.yaml").symlink_to(tmp_path / "model.yaml")
    with pytest.raises(PackageError) as caught:
        snapshot_directory(tmp_path)
    assert caught.value.code == "PACKAGE_PATH_INVALID"


@pytest.mark.parametrize(
    "name,kind",
    [
        ("../escape", tarfile.REGTYPE),
        ("alias", tarfile.SYMTYPE),
        ("alias", tarfile.LNKTYPE),
        ("device", tarfile.CHRTYPE),
    ],
)
def test_archive_special_entries_never_escape(tmp_path, name, kind):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as archive:
        item = tarfile.TarInfo(name)
        item.type = kind
        archive.addfile(item, io.BytesIO())
    with pytest.raises(PackageError):
        receive_archive(io.BytesIO(data.getvalue()))
    assert not (tmp_path / "escape").exists()


def test_missing_and_wrong_kind_refs_are_diagnosed_before_materialization(tmp_path):
    manifest, agent, model = package(tmp_path)
    agent["spec"]["model"]["primary"]["ref"] = "missing"
    with pytest.raises(PackageError) as caught:
        resolve_graph(manifest, {"agent.yaml": agent, "model.yaml": model})
    assert caught.value.code == "PACKAGE_REFERENCE_NOT_FOUND"
    agent["spec"]["model"]["primary"]["ref"] = "support"
    with pytest.raises(PackageError) as caught:
        resolve_graph(manifest, {"agent.yaml": agent, "model.yaml": model})
    assert caught.value.code == "PACKAGE_REFERENCE_KIND"


def test_golden_inventory_hash_is_shared_and_order_independent():
    inventory = [
        {"path": "a", "size_bytes": 1, "sha256": sha256(b"x").hexdigest()},
        {"path": "b", "size_bytes": 2, "sha256": sha256(b"yz").hexdigest()},
    ]
    encoded = json.dumps(
        [[item["path"], item["size_bytes"], item["sha256"]] for item in inventory],
        separators=(",", ":"),
    ).encode()
    assert (
        inventory_digest(inventory)
        == sha256(b"woobe-package@1.0\n" + encoded).hexdigest()
    )
    assert inventory_digest(list(reversed(inventory))) == inventory_digest(inventory)


def test_archive_decompression_budget_includes_padding_and_headers(monkeypatch):
    import gzip
    import modules.package.infra.bundles as bundles

    monkeypatch.setattr(bundles, "MAX_BUNDLE_BYTES", 1024)
    monkeypatch.setattr(bundles, "MAX_DESCRIPTOR_TOTAL", 1024)
    # Tar ends before the compressor does: the rest must still be bounded.
    compressed = gzip.compress(bytes(20000))
    with pytest.raises(PackageError) as caught:
        receive_archive(io.BytesIO(compressed))
    assert caught.value.code == "PACKAGE_LIMIT_EXCEEDED"


def test_parent_directory_case_collisions_are_nonportable():
    registry = PathRegistry()
    registry.register("agents/one.yaml")
    with pytest.raises(PackageError):
        registry.register("Agents/two.yaml")
    with pytest.raises(PackageError):
        registry.register("agents")


@pytest.mark.parametrize(
    "edges,root",
    [
        ([{"from": "a", "to": "b"}, {"from": "b", "to": "a"}], "a"),
        ([], "a"),
        ([{"from": "a", "to": "missing"}], "a"),
        ([{"from": "a", "to": "b"}], "missing"),
    ],
)
def test_invalid_network_topology_is_rejected_before_server_calls(edges, root):
    with pytest.raises(PackageError) as caught:
        validate_network_structure(
            {"root": root, "nodes": [{"key": "a"}, {"key": "b"}], "edges": edges},
            "network.yaml",
        )
    assert caught.value.code == "PACKAGE_NETWORK_INVALID"


def test_large_network_dag_does_not_depend_on_python_recursion_limit():
    nodes = [{"key": str(index)} for index in range(1500)]
    edges = [{"from": str(index), "to": str(index + 1)} for index in range(1499)]
    validate_network_structure(
        {"root": "0", "nodes": nodes, "edges": edges}, "network.yaml"
    )
