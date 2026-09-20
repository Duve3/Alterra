# Alterra architecture — Phase 1

## Current phase

Phase 1 provides a text CLI, session-scoped conversations, a provider-neutral model interface,
and a complete tool-call loop. Voice, memory, integrations, events, scheduling, MCP, and
computer control are deliberately out of scope.

## Boundaries and dependency direction

`main` is the composition root. `core` owns the user-interaction lifecycle and sessions;
`agent` owns model interaction; `tools` owns definitions, validation, registration, and execution.
Tools have no model dependency. Provider-specific code is isolated under `agent/providers`.

```mermaid
flowchart TD
  CLI --> Core[Core: AlterraApplication]
  Core --> Agent[AgentRuntime]
  Agent --> Model[Model provider]
  Model -->|ToolCall| Core
  Core --> Dispatcher[ToolDispatcher]
  Dispatcher --> Registry[ToolRegistry]
  Registry --> Tool[Native tool]
  Tool -->|ToolResult| Core
  Core --> Agent
  Agent -->|AssistantMessage| CLI
```

## Contracts

| Contract | Owner | Purpose |
| --- | --- | --- |
| `UserMessage`, `AssistantMessage`, `ToolCall`, `ToolResult` | `core` | Canonical provider-neutral messages |
| `Session` | `core` | Temporary conversation state; not long-term memory |
| `Model` / `AgentResponse` | `agent` | Replaceable reasoning provider boundary |
| `Tool` / `ToolContext` | `tools` | Capability definition and validated execution |
| `ToolRegistry` / `ToolDispatcher` | `tools` | Availability and operational execution boundary |

## Adding extensions

Add a simple native capability by implementing `Tool`, giving it a namespaced name and Pydantic
argument model, then registering it in the composition root. Do not modify `core/application.py`
or `agent/runtime.py`. Integrations added later belong outside `tools`; their tools should adapt
integration operations into the stable `Tool` contract.

## Configuration and development

Environment variables use the `ALTERRA_` prefix. The default `local` model profile is offline and
supports the Phase 1 demos. Set `ALTERRA_MODEL_PROVIDER=openai` and `ALTERRA_OPENAI_API_KEY` to
use the optional Responses API adapter. Run `uv run pytest` and `uv run ruff check .`.

## Known limitations

The local model is intentionally deterministic and only routes the three Phase 1 tools. It is a
development provider, not a general conversational model. The OpenAI adapter translates the
provider's function calls at the boundary, leaving the rest of Alterra provider-neutral.
