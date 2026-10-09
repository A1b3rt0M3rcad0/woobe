from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from shared.infra.database.base import BaseModel
from shared.infra.asac_record_models import ASaCDraftColumns, ASaCRevisionColumns, ASaCOperationColumns, ASaCCandidateColumns


class ASaCDraftModel(ASaCDraftColumns, BaseModel):
    __tablename__ = "asac_drafts"
    __table_args__ = (
        UniqueConstraint("project_id", "resource_id", "name", name="uq_network_asac_draft_name"),
        UniqueConstraint("project_id", "resource_uid", "name", name="uq_network_asac_draft_uid"),
        CheckConstraint("generation >= 1", name="ck_network_asac_draft_generation"),
        ForeignKeyConstraint(["resource_id"], ["network.networks.id"], ondelete="RESTRICT"),
        {"schema": "network"},
    )


class ASaCRevisionModel(ASaCRevisionColumns, BaseModel):
    __tablename__ = "asac_revisions"
    __table_args__ = (
        UniqueConstraint("project_id", "resource_uid", "revision_id", name="uq_network_asac_revision_identity"),
        ForeignKeyConstraint(["resource_id"], ["network.networks.id"], ondelete="RESTRICT"),
        {"schema": "network"},
    )


class ASaCOperationModel(ASaCOperationColumns, BaseModel):
    __tablename__ = "asac_operations"
    __table_args__ = (
        UniqueConstraint("project_id", "resource_id", "actor", "operation_id", name="uq_network_asac_operation_identity"),
        {"schema": "network"},
    )


class ASaCResourceModel(BaseModel):
    __tablename__ = "asac_resources"
    from sqlalchemy.orm import Mapped
    from uuid import UUID
    project_id: Mapped[UUID]
    resource_id: Mapped[UUID]
    resource_uid: Mapped[UUID]
    __table_args__ = (
        UniqueConstraint("project_id", "resource_id", name="uq_network_asac_resource_native"),
        UniqueConstraint("project_id", "resource_uid", name="uq_network_asac_resource_uid"),
        ForeignKeyConstraint(["resource_id"], ["network.networks.id"], ondelete="RESTRICT"),
        {"schema": "network"},
    )


class ASaCCandidateModel(ASaCCandidateColumns, BaseModel):
    __tablename__ = "asac_candidates"
    __table_args__ = (
        UniqueConstraint("project_id", "resource_id", "actor", "operation_id", name="uq_network_asac_candidate_operation"),
        CheckConstraint("draft_generation >= 1", name="ck_network_asac_candidate_generation"),
        CheckConstraint("state IN ('preparing', 'ready', 'rejected')", name="ck_network_asac_candidate_state"),
        ForeignKeyConstraint(["resource_id"], ["network.networks.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["draft_id"], ["network.asac_drafts.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["project_id", "resource_uid", "revision_id"], ["network.asac_revisions.project_id", "network.asac_revisions.resource_uid", "network.asac_revisions.revision_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["root_snapshot_id"], ["network.network_versions.id"], ondelete="RESTRICT"),
        {"schema": "network"},
    )


from shared.infra.asac_record_models import ASaCEvaluationColumns

class ASaCEvaluationModel(ASaCEvaluationColumns, BaseModel):
    __tablename__ = "asac_evaluations"
    __table_args__ = (
        UniqueConstraint("project_id", "resource_id", "actor", "operation_id", name="uq_network_asac_evaluation_operation"),
        CheckConstraint("state IN ('accepted', 'running', 'passed', 'failed', 'uncertain')", name="ck_network_asac_evaluation_state"),
        ForeignKeyConstraint(["resource_id"], ["network.networks.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["candidate_id"], ["network.asac_candidates.id"], ondelete="RESTRICT"),
        {"schema": "network"},
    )
