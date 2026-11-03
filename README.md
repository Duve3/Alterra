# Alterra

A modular personal AI assistant platform inspired by the ALTERRA computer from Subnautica.

## Status: MVP

The current implementation is Stage 2 (First Real Integration):

- ✅ OpenRouter LLM integration (single provider)
- ✅ CLI interface with conversation history
- ✅ Tool infrastructure (registry, dispatcher, execution boundary)
- ✅ **Filesystem integration** (`filesystem.read`, `write`, `list`, `search`)
- ✅ In-memory session management
- ✅ Standard logging (console + rotating file)
- ✅ TOML + environment variable configuration

**Out of scope for Stage 2:** voice, scheduler, events, persistent memory, demo tools, multi-provider, web UI.

---

## Quick Start

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) for dependency management
- OpenRouter API key (get one at https://openrouter.ai/keys)

### Installation

```bash
git clone https://github.com/duve3/alterra.git
cd alterra
uv sync
```

### Configuration

```bash
cp .env.example .env
# Edit .env and add your OpenRouter API key
```

Required:
```bash
ALTERRA_OPENROUTER_API_KEY=sk-or-v1-...
```

Optional (shown with defaults):
```bash
ALTERRA_MODEL=openrouter/auto
ALTERRA_TEMPERATURE=0.7
ALTERRA_MAX_TOKENS=2048
ALTERRA_ALLOW_PROVIDER_FALLBACKS=false
ALTERRA_LOG_LEVEL=INFO
ALTERRA_MAX_TOOL_ROUNDS=8
```

You can also configure via `config/alterra.toml` (environment variables take precedence).

### Run

```bash
uv run python -m alterra
```

```
Alterra
Connected to OpenRouter
Model: openrouter/auto
Type 'exit' or 'quit' to leave, 'clear' to reset conversation.

> Hello Alterra.

Alterra:
Hello! How can I help you today?
```

Commands:
- `exit` / `quit` — Leave
- `clear` — Reset conversation history

---

## Project Structure

```
alterra/
├── config/
│   └── alterra.toml          # Application configuration
├── docs/
│   └── architecture.md       # Architecture documentation
├── src/
│   └── alterra/
│       ├── __main__.py       # Entry point
│       ├── app.py            # Composition root
│       ├── cli.py            # CLI interface
│       ├── logging_setup.py  # Standard logging config
│       ├── core/             # Application orchestration
│       │   ├── application.py
│       │   ├── config.py
│       │   ├── errors.py
│       │   ├── messages.py
│       │   └── session.py
│       ├── agent/            # Model interaction
│       │   ├── model.py
│       │   ├── runtime.py
│       │   └── providers/
│       │       └── openrouter.py
│       ├── integrations/     # Real capabilities (Stage 2+)
│       │   └── filesystem/   # File read/write/list/search
│       │       ├── __init__.py
│       │       └── tools.py
│       └── tools/            # Capability infrastructure
│           ├── base.py
│           ├── registry.py
│           └── dispatcher.py
├── tests/
│   ├── agent/
│   ├── core/
│   └── tools/
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## Architecture Highlights

### Provider Isolation

`agent/providers/openrouter.py` is the **only** place that imports `httpx` or knows about OpenRouter's API. The rest of the codebase uses the provider-neutral `Model` protocol:

```python
class Model(Protocol):
    async def generate(self, messages: list[ConversationMessage], tools: list[dict]) -> AgentResponse: ...
```

Adding a new provider (Ollama, llama.cpp, etc.) means implementing this protocol — **no changes to core or agent runtime**.

### Tool Execution Safety

```
Model requests tool
       │
       ▼
Find registered tool
       │
       ▼
Validate arguments (Pydantic)
       │
       ▼
Enforce timeout (asyncio.timeout)
       │
       ▼
Execute capability
       │
       ▼
Return structured ToolResult
```

- Only registered tools execute
- Arguments validated before execution
- Timeouts enforced per-tool
- Errors returned as `ToolResult(success=False)` — model sees them and can recover

### Configuration Precedence

1. Code defaults
2. `config/alterra.toml`
3. `.env` (prefix `ALTERRA_`)
4. Explicit constructor args

Missing required config (API key) → clear `ConfigurationError` at startup.

---

## Development

### Running Tests

```bash
uv run pytest -v
```

### Linting

```bash
uv run ruff check src/
uv run ruff check --fix src/  # auto-fix
```

### Adding a Real Capability

When you need a real tool (not a demo):

1. Create integration module (e.g., `src/alterra/integrations/computer.py`)
2. Implement `Tool` subclass with Pydantic `arguments_model`
3. Register in `app.py`:
   ```python
   from alterra.integrations.computer import OpenApplicationTool
   registry.register(OpenApplicationTool())
   ```
4. Add tests in `tests/tools/test_computer_tools.py`

No changes to `core/`, `agent/`, or `cli/` required.

---

## License

MIT — see [LICENSE](LICENSE) for details.

Third-party dependencies retain their own licenses.