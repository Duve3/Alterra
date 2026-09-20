"""Application-owned authorization policy and confirmation contracts.

The agent may propose a tool call, but it can never authorize one.  Policy is evaluated by
the application before the dispatcher is allowed to execute a capability.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolPolicyMetadata(BaseModel):
    risk_level: RiskLevel = RiskLevel.NONE
    requires_confirmation: bool = False
    timeout_seconds: float = Field(default=30, gt=0, le=300)


class PolicyRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    metadata: ToolPolicyMetadata
    session_id: str


class PolicyDecision(BaseModel):
    allowed: bool
    requires_confirmation: bool = False
    reason: str | None = None


class Policy(Protocol):
    def evaluate(self, request: PolicyRequest) -> PolicyDecision: ...


class ConfirmationHandler(Protocol):
    async def confirm(self, request: PolicyRequest) -> bool: ...


class RejectingConfirmationHandler:
    """Safe default for non-interactive application hosts."""

    async def confirm(self, request: PolicyRequest) -> bool:
        return False


class DefaultPolicy:
    """A deterministic, configurable baseline policy for native tools."""

    def __init__(
        self,
        *,
        denied_tools: set[str] | None = None,
        confirmation_risks: set[RiskLevel] | None = None,
        risk_overrides: dict[str, RiskLevel] | None = None,
    ) -> None:
        self._denied_tools = denied_tools or set()
        self._confirmation_risks = confirmation_risks or {
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        }
        self._risk_overrides = risk_overrides or {}

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        if request.tool_name in self._denied_tools:
            return PolicyDecision(allowed=False, reason=f"Policy denies {request.tool_name}")
        risk = self._risk_overrides.get(request.tool_name, request.metadata.risk_level)
        return PolicyDecision(
            allowed=True,
            requires_confirmation=request.metadata.requires_confirmation or risk in self._confirmation_risks,
            reason=f"{risk.value}-risk capability",
        )
