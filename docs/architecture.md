# Alterra Architecture — MVP

## Overview

Alterra is a modular personal AI assistant platform. The MVP implements a minimal, working foundation:

- **OpenRouter** as the sole LLM provider
- **CLI** as the primary interface
- **Tool infrastructure** (registry, dispatcher, execution boundary) — empty in production
- **In-memory conversation history** per session
- **Standard logging** (console + rotating file)
- **TOML + env configuration**

Everything else (voice, scheduler, events, persistent memory, demo tools, multi-provider) is explicitly out of scope for MVP.

---

## Boundaries and Dependency Direction

```
┌─────────────────────────────────────────────────────────────┐
│                      __main__.py                            │
│                        (entry)                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                         app.py                               │
│                  (composition root)                          │
│  • Load config (Settings)                                    │
│  • Setup logging                                             │
│  • Construct OpenRouterModel                                 │
│  • Build empty ToolRegistry                                  │
│  • Build AgentRuntime + AlterraApplication                   │
│  • Start CLI                                                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │  CLI     │ │  OpenRouterModel │  ToolRegistry │
    │ (cli.py) │ │ (providers)      │ (tools)       │
    └──────────┘ └────────────────┘ └─────────────┘
                      ▲                    ▲
                      │                    │
                ┌─────┴─────┐      ┌───────┴───────┐
                │AgentRuntime│      │  ToolDispatcher │
                └───────────┘      └──────────────┘
                      │
                      ▼
              ┌──────────────┐
              │AlterraApplication│
              │(core/application)│
              └──────────────┘
```

**Key rules:**
- `app.py` is the **only** place that constructs concrete implementations
- `core/` knows nothing about OpenRouter, httpx, or specific tools
- `agent/` knows nothing about CLI, config, or logging
- `tools/` knows nothing about models, sessions, or providers

---

## Contracts

| Contract | Owner | Purpose |
| --- | --- | --- |
| `UserMessage`, `AssistantMessage`, `ToolCall`, `ToolResult` | `core` | Provider-neutral messages |
| `Session` | `core` | Temporary conversation state (in-memory) |
| `Model` / `AgentResponse` | `agent` | Replaceable reasoning provider boundary |
| `Tool` / `ToolContext` | `tools` | Capability definition + validated execution |
| `ToolRegistry` / `ToolDispatcher` | `tools` | Availability and execution boundary |

---

## Core Components

### `core/application.py` — `AlterraApplication`

Single owner of the conversation loop:

```python
async def handle_message(self, message: UserMessage) -> AssistantMessage:
    session = self.session(message.session_id)
    session.append(message)
    for _ in range(self._max_tool_rounds):
        response = await self._agent.generate(session.messages)
        if response.message is not None:
            session.append(response.message)
            return response.message
        if not response.tool_calls:
            raise AgentError("Model returned neither message nor tool calls")
        # Add assistant message with tool calls to history
        assistant_msg = AssistantMessage(content="", tool_calls=response.tool_calls)
        session.append(assistant_msg)
        for call in response.tool_calls:
            result = await self._dispatcher.dispatch(call, session_id=session.id)
            session.append(result)
    raise AgentError(f"Tool round limit ({self._max_tool_rounds}) exceeded")
```

- Maintains per-session `Session` objects (in-memory `dict`)
- Coordinates model → tool → model cycle
- Enforces `max_tool_rounds` to prevent infinite loops
- **No policy/confirmation system** — tools execute directly (MVP)

### `core/config.py` — `Settings`

Pydantic-settings model loading from:
1. Code defaults
2. `.env` (prefix `ALTERRA_`)
3. Explicit constructor args

```python
class Settings(BaseSettings):
    model: str = "openrouter/auto"
    temperature: float = 0.7
    max_tokens: int = 2048
    allow_provider_fallbacks: bool = False  # Critical for reproducibility
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    log_level: str = "INFO"
    max_tool_rounds: int = 8
```

**No fallback providers/models** — if the configured model fails, error is surfaced.

### `core/messages.py` — Canonical message types

```python
class UserMessage(Message):
    role: Literal["user"] = "user"
    content: str
    session_id: str = "default"

class AssistantMessage(Message):
    role: Literal["assistant"] = "assistant"
    content: str = ""
    tool_calls: list[ToolCall] = []

class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = {}

class ToolResult(Message):
    role: Literal["tool"] = "tool"
    tool_call_id: str
    name: str
    success: bool
    data: Any = None
    error: str | None = None
```

- **No SDK types leak** — OpenRouter responses normalized here
- `AssistantMessage` carries `tool_calls` for history reconstruction

### `core/session.py` — `Session`

```python
class Session(BaseModel):
    id: str
    messages: list[ConversationMessage] = []
    metadata: dict[str, str] = {}
    
    def append(self, message: ConversationMessage) -> None:
        self.messages.append(message)
```

- Pure in-memory, per `session_id`
- No persistence (MVP)
- `ConversationMessage = UserMessage | AssistantMessage | ToolResult`

---

## Agent Layer

### `agent/model.py` — Provider-neutral interface

```python
class AgentResponse(BaseModel):
    message: AssistantMessage | None = None
    tool_calls: list[ToolCall] = []
    # Validator: exactly one of message XOR tool_calls

class Model(Protocol):
    async def generate(self, messages: list[ConversationMessage], tools: list[dict]) -> AgentResponse: ...
```

### `agent/runtime.py` — `AgentRuntime`

```python
class AgentRuntime:
    def __init__(self, model: Model, tools: ToolRegistry):
        self._model = model
        self._tools = tools

    async def generate(self, messages: list[ConversationMessage]) -> AgentResponse:
        return await self._model.generate(messages, self._tools.definitions())
```

- Thin adapter: holds model + tool registry, passes tool definitions to model
- No business logic

### `agent/providers/openrouter.py` — `OpenRouterModel`

Uses OpenAI-compatible **Chat Completions** endpoint via `httpx` (no SDK dependency).

```python
class OpenRouterModel:
    def __init__(self, *, api_key: str, model: str, base_url: str = "...",
                 temperature: float = 0.7, max_tokens: int = 2048,
                 allow_provider_fallbacks: bool = False, client: httpx.AsyncClient | None = None):
        ...
    
    async def generate(self, messages, tools) -> AgentResponse:
        payload = {
            "model": self._model,
            "messages": [...],
            "tools": [...],
            "tool_choice": "auto" if tools else None,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "provider": {"allow_fallbacks": self._allow_provider_fallbacks},
        }
        # POST to /chat/completions, normalize to AgentResponse
```

- **Single long-lived `AsyncClient`** (created in `__init__`, closed in `close()`)
- `provider: {allow_fallbacks: false}` sent explicitly — **no silent model switching**
- Inject `client` for testing

---

## Tools Layer

### `tools/base.py` — `Tool` contract

```python
class Tool(ABC):
    name: ClassVar[str]           # e.g. "computer.open_application"
    description: ClassVar[str]    # Human + model readable
    arguments_model: ClassVar[type[BaseModel]]  # Pydantic schema
    timeout_seconds: ClassVar[float] = 30.0
    
    @classmethod
    def definition(cls) -> dict: ...
    
    @abstractmethod
    async def execute(self, arguments: BaseModel, context: ToolContext) -> Any: ...
```

- **No policy metadata** in MVP — tools execute when called
- `definition()` produces JSON schema for model

### `tools/registry.py` — `ToolRegistry`

```python
class ToolRegistry:
    def __init__(self): self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None: ...
    def get(self, name: str) -> Tool: ...
    def definitions(self) -> list[dict]: ...
```

- Simple dict lookup, duplicate name → `ValueError`
- `definitions()` called by `AgentRuntime` for each model request

### `tools/dispatcher.py` — `ToolDispatcher`

```python
class ToolDispatcher:
    def __init__(self, registry: ToolRegistry): ...
    
    async def dispatch(self, call: ToolCall, *, session_id: str) -> ToolResult:
        tool = self._registry.get(call.name)  # raises ToolNotFoundError
        arguments = tool.arguments_model.model_validate(call.arguments)
        async with asyncio.timeout(tool.timeout_seconds):
            data = await tool.execute(arguments, ToolContext(session_id=session_id))
        return ToolResult(tool_call_id=call.id, name=call.name, success=True, data=data)
```

- Validates args against `arguments_model`
- Enforces `timeout_seconds` via `asyncio.timeout`
- Catches `ValidationError`, `ValueError`, `TimeoutError` → `ToolResult(success=False)`

---

## CLI

### `cli.py` — `run_cli()`

```python
async def run_cli(application: AlterraApplication, model_name: str) -> None:
    print(f"Alterra\nConnected to OpenRouter\nModel: {model_name}")
    while (text := input("> ").strip()).lower() not in {"exit", "quit"}:
        if text.lower() == "clear":
            application._sessions.pop("cli", None)
            print("(conversation cleared)")
            continue
        reply = await application.handle_message(UserMessage(content=text, session_id="cli"))
        print(f"Alterra: {reply.content}")
```

- Single session ID: `"cli"`
- Commands: `exit`/`quit`, `clear`
- Delegates all LLM interaction to `AlterraApplication`

---

## Configuration Files

### `config/alterra.toml`

```toml
[application]
name = "Alterra"
environment = "development"

[llm]
model = "openrouter/auto"
temperature = 0.7
max_tokens = 2048
allow_provider_fallbacks = false

[logging]
level = "INFO"
console = true
file = true
```

### `.env` (not committed)

```bash
ALTERRA_OPENROUTER_API_KEY=sk-or-v1-...
ALTERRA_MODEL=openrouter/auto
ALTERRA_TEMPERATURE=0.7
ALTERRA_MAX_TOKENS=2048
ALTERRA_ALLOW_PROVIDER_FALLBACKS=false
ALTERRA_LOG_LEVEL=INFO
ALTERRA_MAX_TOOL_ROUNDS=8
```

---

## Running

```bash
# Install deps
uv sync

# Run CLI
uv run python -m alterra

# Run tests
uv run pytest -v

# Lint
uv run ruff check src/
```

---

## Adding Capabilities (Post-MVP)

When a real capability is needed:

1. **Implement integration** (e.g., `integrations/computer.py`) — talks to OS, APIs, etc.
2. **Create tool** in `tools/` or integration package:
   ```python
   class OpenApplicationTool(Tool):
       name = "computer.open_application"
       description = "Open a macOS/Windows/Linux application by bundle ID or path"
       class Args(BaseModel): app_id: str
       arguments_model = Args
       async def execute(self, args, ctx): ...
   ```
3. **Register in `app.py`**:
   ```python
   from integrations.computer import OpenApplicationTool
   registry.register(OpenApplicationTool())
   ```
4. **Test** — add to `tests/tools/test_computer_tools.py`

**No changes to** `core/`, `agent/`, or `cli/` required.

---

## Known Limitations (MVP)

| Limitation | Reason | Resolution |
| --- | --- | --- |
| Empty tool registry | No demo tools in production | Add real tools when needed |
| No persistent memory | Out of scope | Add `SQLiteMemoryStore` + `memory.store/retrieve` tools |
| No voice | Out of scope | Add `voice/` package, reuse `AlterraApplication` |
| No scheduler | Out of scope | Add `scheduler/` package |
| Single provider | MVP focus | Add `OllamaProvider`, `LlamaCppProvider` implementing `Model` |
| In-memory sessions only | MVP | Add persistence layer later |

---

## Design Principles (from project brief)

1. **Working software over frameworks** — one assistant loop, not multi-agent orchestration
2. **Less code** — no abstract bases without multiple implementations
3. **No hypothetical requirements** — build only what's needed today
4. **Deliberate boundaries** — `Model` protocol prevents OpenRouter leakage
5. **Research before deps** — `httpx` + `pydantic` only; no LangChain, no structlog