"""Model-provider adapters. Provider types do not escape this package."""

from .local import LocalModel
from .openai import OpenAIResponsesModel

__all__ = ["LocalModel", "OpenAIResponsesModel"]
