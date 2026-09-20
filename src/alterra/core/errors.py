"""Application-owned error types."""


class AlterraError(Exception):
    """Base exception for expected Alterra failures."""


class ConfigurationError(AlterraError):
    """Raised when configuration cannot construct the requested application."""


class SessionError(AlterraError):
    """Raised for invalid session operations."""


class ToolError(AlterraError):
    """Raised for an expected tool failure."""


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is not registered."""


class AgentError(AlterraError):
    """Raised for an expected model or agent failure."""
