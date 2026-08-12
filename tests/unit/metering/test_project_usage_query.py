from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from modules.metering.application.dtos.project_usage import ProjectUsageQuery


def test_project_usage_defaults_to_daily_thirty_day_window():
    query = ProjectUsageQuery(project_id=uuid4())
    assert query.bucket == "day"
    assert query.operation == "all"
    assert query.group_by == "agent"
    assert query.from_ is not None
    assert query.to is not None
    assert timedelta(days=29) < query.to - query.from_ <= timedelta(days=30)


def test_project_usage_uses_hour_bucket_for_short_window():
    end = datetime.now(UTC)
    query = ProjectUsageQuery.model_validate(
        {
            "project_id": uuid4(),
            "from": (end - timedelta(hours=24)).isoformat(),
            "to": end.isoformat(),
        }
    )
    assert query.bucket == "hour"


def test_project_usage_preserves_network_scope():
    network_id = uuid4()
    query = ProjectUsageQuery(
        project_id=uuid4(),
        operation="network",
        network_id=network_id,
        group_by="network",
    )
    assert query.operation == "network"
    assert query.network_id == network_id
    assert query.group_by == "network"


def test_direct_agent_operation_cannot_group_by_network():
    query = ProjectUsageQuery(
        project_id=uuid4(),
        operation="agent",
        group_by="network",
    )
    assert query.group_by == "agent"


def test_project_usage_rejects_ranges_above_ninety_days():
    end = datetime.now(UTC)
    with pytest.raises(ValidationError):
        ProjectUsageQuery.model_validate(
            {
                "project_id": uuid4(),
                "from": (end - timedelta(days=91)).isoformat(),
                "to": end.isoformat(),
            }
        )
