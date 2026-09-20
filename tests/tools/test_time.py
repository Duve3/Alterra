import pytest

from alterra.core.errors import ToolError
from alterra.tools.base import ToolContext
from alterra.tools.builtin.time import TimeArguments, TimeTool


async def test_time_tool_returns_requested_timezone() -> None:
    result = await TimeTool().execute(TimeArguments(timezone="UTC"), ToolContext(session_id="test"))
    assert result["timezone"] == "UTC"
    assert result["utc"].endswith("+00:00")


async def test_time_tool_rejects_invalid_timezone() -> None:
    with pytest.raises(ToolError, match="Unknown timezone"):
        await TimeTool().execute(TimeArguments(timezone="No/Such_Zone"), ToolContext(session_id="test"))
