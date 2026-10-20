from importlib.metadata import PackageNotFoundError, version


def probe_distribution(name: str, expected_version: str):
    """Inspect installed metadata without importing a parser or downloading data."""
    try:
        installed = version(name)
    except PackageNotFoundError:
        return False, 'dependency_not_installed'
    if installed != expected_version:
        return False, 'dependency_version_mismatch'
    return True, None
