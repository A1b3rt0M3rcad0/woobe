from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
METERING_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "metering"


def test_metering_service_dir_does_not_exist():
    service_dir = METERING_DIR / "service"
    assert not service_dir.is_dir(), "metering/service/ must not exist"


def test_metering_infra_flat_models_does_not_exist():
    assert not (METERING_DIR / "infra" / "models.py").is_file(), \
        "metering/infra/models.py must not exist (use infra/database/models.py)"


def test_metering_infra_flat_repositories_does_not_exist():
    assert not (METERING_DIR / "infra" / "repositories.py").is_file(), \
        "metering/infra/repositories.py must not exist (use infra/database/repositories.py)"


def test_metering_infra_flat_mappers_does_not_exist():
    assert not (METERING_DIR / "infra" / "mappers.py").is_file(), \
        "metering/infra/mappers.py must not exist (use infra/database/mappers.py)"


def test_metering_canonical_database_models_exist():
    assert (METERING_DIR / "infra" / "database" / "models.py").is_file(), \
        "metering/infra/database/models.py must exist"


def test_metering_canonical_database_repositories_exist():
    assert (METERING_DIR / "infra" / "database" / "repositories.py").is_file(), \
        "metering/infra/database/repositories.py must exist"


def test_metering_canonical_database_mappers_exist():
    assert (METERING_DIR / "infra" / "database" / "mappers.py").is_file(), \
        "metering/infra/database/mappers.py must exist"


def test_metering_application_dtos_exist():
    assert (METERING_DIR / "application" / "dtos" / "metering_dtos.py").is_file(), \
        "metering/application/dtos/metering_dtos.py must exist"


def test_metering_application_use_cases_exist():
    assert (METERING_DIR / "application" / "use_cases" / "metering_use_cases.py").is_file(), \
        "metering/application/use_cases/metering_use_cases.py must exist"
