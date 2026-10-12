from modules.agent.domain.entities import AgentRelease
from modules.agent.presentation.mappers import (
    list_releases_to_response,
    release_to_response,
)


def test_release_detail_exposes_exact_primary_and_fallback_specs_without_catalog_lookup():
    release = AgentRelease(
        model_spec_snapshot={"pricing": {"input_cost_per_1m_tokens": 1}},
        model_spec_hash="primary-capture",
        fallback_model_spec_snapshot={"pricing": {"input_cost_per_1m_tokens": 2}},
        fallback_model_spec_hash="fallback-capture",
    )
    detail = release_to_response(release).model_dump()
    assert detail["model_spec_snapshot"] == release.model_spec_snapshot
    assert detail["model_spec_hash"] == "primary-capture"
    assert (
        detail["fallback_model_spec_snapshot"] == release.fallback_model_spec_snapshot
    )
    assert detail["fallback_model_spec_hash"] == "fallback-capture"
    summary = list_releases_to_response(release).model_dump()
    assert summary["model_spec_hash"] == "primary-capture"
    assert summary["fallback_model_spec_hash"] == "fallback-capture"
    assert "model_spec_snapshot" not in summary


def test_legacy_release_with_no_captured_spec_stays_null_in_detail_and_list():
    release = AgentRelease()
    detail = release_to_response(release).model_dump()
    summary = list_releases_to_response(release).model_dump()
    assert detail["model_spec_snapshot"] is None
    assert detail["model_spec_hash"] is None
    assert detail["fallback_model_spec_snapshot"] is None
    assert summary["model_spec_hash"] is None
