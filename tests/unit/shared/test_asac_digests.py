from decimal import Decimal
import json
from pathlib import Path

import pytest

from shared.contracts.asac import asac_digest


def test_shared_go_python_asac_digests():
    fixtures = json.loads((Path(__file__).parents[2] / "contract/fixtures/asac-digests.json").read_text())
    for fixture in fixtures:
        value = json.loads(fixture["json"], parse_float=Decimal)
        assert asac_digest(fixture["scope"], value) == fixture["digest"]


def test_asac_preserves_types_and_normalizes_exact_numbers():
    assert asac_digest("definition", 1) == asac_digest("definition", Decimal("1.00"))
    assert asac_digest("definition", 1) != asac_digest("definition", "1")
    assert asac_digest("definition", {}) != asac_digest("definition", {"value": None})
    with pytest.raises(ValueError):
        asac_digest("definition", float("nan"))


def test_canonical_numbers_have_bounded_cost():
    from decimal import Decimal
    import pytest
    for value in (Decimal("1e999999999"), Decimal("1e-999999999"), Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(ValueError):
            asac_digest("definition", value)
