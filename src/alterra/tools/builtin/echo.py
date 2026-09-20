from pydantic import BaseModel, Field

from ..base import Tool, ToolContext


class EchoArguments(BaseModel):
    text: str = Field(description="Text to return exactly as provided.")


class EchoTool(Tool):
    name = "echo.repeat"
    description = "Return the provided text unchanged."
    arguments_model = EchoArguments

    async def execute(self, arguments: EchoArguments, context: ToolContext) -> str:
        return arguments.text
