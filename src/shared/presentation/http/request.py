from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from shared.security.principal import SecurityPrincipal


class Request(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    principal: SecurityPrincipal | None = None
    user: str | None = None
    url: str | None = None
    method: str | None = None
    headers: dict[str, Any] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)
    client_ip: str | None = None
    body: Any = None
    query_params: dict[str, Any] = Field(default_factory=dict)
    path_params: dict[str, Any] = Field(default_factory=dict)

    @property
    def query(self) -> dict[str, Any]:
        return self.query_params

    @property
    def params(self) -> dict[str, Any]:
        return self.path_params
