from uuid import UUID

from pydantic import BaseModel


class GetNetworkRunDiagnosticsInput(BaseModel):
    execution_id: UUID
    project_id: UUID
