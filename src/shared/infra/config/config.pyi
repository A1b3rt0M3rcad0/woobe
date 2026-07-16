from typing import Any

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    def __init__(self, **values: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
