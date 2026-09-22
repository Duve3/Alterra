from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

from alterra.core.policy import RiskLevel, ToolPolicyMetadata

from ...core.errors import ToolError
from ..base import Tool, ToolContext


class TimeArguments(BaseModel):
    timezone: str = Field(
        default="America/Los_Angeles",
        description="IANA timezone name, for example America/Los_Angeles.",
    )


class TimeTool(Tool):
    name = "time.current"
    description = "Get the current time in an IANA timezone."
    arguments_model = TimeArguments
    metadata = ToolPolicyMetadata(
        risk_level=RiskLevel.NONE, timeout_seconds=5
    )  # if time is not retrieved in 5 seconds, stop it

    async def execute(self, arguments: BaseModel, context: ToolContext) -> dict[str, str]:
        validated = self.arguments_model.model_validate(arguments.model_dump())
        tz = validated.timezone  # type: ignore[attr-defined]
        try:
            now = datetime.now(ZoneInfo(tz))
        except ZoneInfoNotFoundError as error:
            raise ToolError(f"Unknown timezone: {tz}") from error
        return {
            "iso": now.isoformat(),
            "timezone": tz,
            "utc": now.astimezone(UTC).isoformat(),
            "posix": str(now.timestamp()),
        }
