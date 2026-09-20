"""Model-provider adapters. Provider types do not escape this package."""

from .local import LocalModel
from .openai import OpenAIResponsesModel
from .openrouter import OpenRouterResponsesModel

__all__ = ["LocalModel", "OpenAIResponsesModel", "OpenRouterResponsesModel"]
