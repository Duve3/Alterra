"""A deliberately narrow arithmetic tool with no arbitrary code execution."""

from __future__ import annotations

import ast
import operator

from pydantic import BaseModel, Field

from ...core.errors import ToolError
from ..base import Tool, ToolContext


class CalculatorArguments(BaseModel):
    expression: str = Field(
        description="Arithmetic expression using numbers and +, -, *, /, //, %, or **."
    )


class CalculatorTool(Tool):
    name = "calculator.evaluate"
    description = (
        "Evaluate a basic arithmetic expression. It cannot execute code or access variables."
    )
    arguments_model = CalculatorArguments

    async def execute(self, arguments: BaseModel, context: ToolContext) -> int | float:
        validated = self.arguments_model.model_validate(arguments.model_dump())
        try:
            parsed = ast.parse(validated.expression, mode="eval")  # type: ignore[attr-defined]
            value = self._evaluate(parsed.body)
        except (SyntaxError, TypeError, ValueError, ZeroDivisionError) as error:
            raise ToolError(f"Invalid arithmetic expression: {error}") from error
        return value

    def _evaluate(self, node: ast.expr) -> int | float:
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
        ):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in {ast.UAdd, ast.USub}:
            return (
                operator.pos(self._evaluate(node.operand))
                if isinstance(node.op, ast.UAdd)
                else operator.neg(self._evaluate(node.operand))
            )
        operations = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
        }
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](self._evaluate(node.left), self._evaluate(node.right))
        raise ValueError("only numeric arithmetic operators are permitted")
