# Alterra

Alterra is a modular personal AI assistant platform. Phase 1 establishes a text-only,
provider-neutral message → agent → tool → result → agent loop.

```powershell
uv run alterra
```

The default local profile works without credentials:

```text
> What is 15 * 4?
Alterra: 60
```

See [the architecture guide](docs/architecture.md) for boundaries, configuration, and extension rules.

## OpenRouter

To use OpenRouter, place the following in `.env` (or set equivalent environment variables):

```env
ALTERRA_MODEL_PROVIDER=openrouter
ALTERRA_OPENROUTER_API_KEY=your-openrouter-key
ALTERRA_OPENROUTER_MODEL=openai/gpt-5
# Optional attribution metadata
ALTERRA_OPENROUTER_SITE_URL=https://example.com
ALTERRA_OPENROUTER_APP_NAME=Alterra
```

Alterra uses OpenRouter's Responses-compatible endpoint while keeping its model interface and
tool protocol provider-neutral.
