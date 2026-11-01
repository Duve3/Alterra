"""The stable public capability contract for all native and future external tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel


class ToolContext(BaseModel):
    session_id: str


ArgumentsT = TypeVar("ArgumentsT", bound=BaseModel)


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    arguments_model: ClassVar[type[BaseModel]]
    timeout_seconds: ClassVar[float] = 30.0

    @classmethod
    def definition(cls) -> dict[str, Any]:
        return {
            "name": cls.name,
            "description": cls.description,
            "input_schema": cls.arguments_model.model_json_schema(),
        }

    @abstractmethod
    async def execute(self, arguments: BaseModel, context: ToolContext) -> Any:
        """Execute validated input and return application-level data, not provider data."""