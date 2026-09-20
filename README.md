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
