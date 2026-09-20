"""OpenRouter adapter using its OpenAI-compatible Responses API."""

from .openai import OpenAIResponsesModel


class OpenRouterResponsesModel(OpenAIResponsesModel):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        site_url: str | None = None,
        app_name: str | None = None,
    ):
        extra_headers = {
            key: value
            for key, value in {
                "HTTP-Referer": site_url,
                "X-OpenRouter-Title": app_name,
            }.items()
            if value
        }
        super().__init__(api_key=api_key, model=model, base_url=base_url, extra_headers=extra_headers)
