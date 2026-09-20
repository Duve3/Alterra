"""Capability definitions, registration, validation, and dispatch."""

from .dispatcher import ToolDispatcher
from .registry import ToolRegistry

__all__ = ["ToolDispatcher", "ToolRegistry"]
