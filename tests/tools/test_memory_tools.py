"""Tests for memory tools."""

import pytest

from alterra.core.messages import ToolCall
from alterra.core.policy import RiskLevel
from alterra.memory import SQLiteMemoryStore
from alterra.tools.builtin import MemoryDeleteTool, MemoryRetrieveTool, MemoryStoreTool
from alterra.tools.dispatcher import ToolDispatcher
from alterra.tools.registry import ToolRegistry


@pytest.fixture
def memory_store(tmp_path) -> SQLiteMemoryStore:
    return SQLiteMemoryStore(tmp_path / "test_memory.db")


@pytest.fixture
def registry(memory_store: SQLiteMemoryStore) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(MemoryStoreTool(memory_store))
    reg.register(MemoryRetrieveTool(memory_store))
    reg.register(MemoryDeleteTool(memory_store))
    return reg


@pytest.fixture
def dispatcher(registry: ToolRegistry) -> ToolDispatcher:
    return ToolDispatcher(registry)


async def test_memory_store_tool(dispatcher: ToolDispatcher) -> None:
    result = await dispatcher.dispatch(
        ToolCall(
            name="memory.store",
            arguments={"content": "User likes coffee", "scope": "user", "scope_id": "user-123"},
        ),
        session_id="test",
    )
    assert result.success is True
    assert result.data["content"] == "User likes coffee"
    assert result.data["scope"] == "user"
    assert result.data["scope_id"] == "user-123"
    assert "id" in result.data


async def test_memory_store_tool_with_defaults(dispatcher: ToolDispatcher) -> None:
    result = await dispatcher.dispatch(
        ToolCall(name="memory.store", arguments={"content": "Default scope test"}),
        session_id="test",
    )
    assert result.success is True
    assert result.data["scope"] == "user"
    assert result.data["scope_id"] is None


async def test_memory_retrieve_tool(dispatcher: ToolDispatcher) -> None:
    # First store some memories
    await dispatcher.dispatch(
        ToolCall(
            name="memory.store",
            arguments={"content": "User prefers dark mode", "scope": "user", "scope_id": "user-1"},
        ),
        session_id="test",
    )
    await dispatcher.dispatch(
        ToolCall(
            name="memory.store",
            arguments={"content": "User likes cats", "scope": "user", "scope_id": "user-1"},
        ),
        session_id="test",
    )
    await dispatcher.dispatch(
        ToolCall(
            name="memory.store",
            arguments={"content": "Global setting: language=en", "scope": "global"},
        ),
        session_id="test",
    )

    # Retrieve by query
    result = await dispatcher.dispatch(
        ToolCall(
            name="memory.retrieve",
            arguments={"query": "dark mode", "scope": "user", "scope_id": "user-1"},
        ),
        session_id="test",
    )
    assert result.success is True
    assert result.data["count"] == 1
    assert "dark mode" in result.data["results"][0]["content"].lower()


async def test_memory_retrieve_tool_filters_by_scope(dispatcher: ToolDispatcher) -> None:
    await dispatcher.dispatch(
        ToolCall(
            name="memory.store",
            arguments={"content": "User specific", "scope": "user", "scope_id": "user-1"},
        ),
        session_id="test",
    )
    await dispatcher.dispatch(
        ToolCall(name="memory.store", arguments={"content": "Global info", "scope": "global"}),
        session_id="test",
    )

    result = await dispatcher.dispatch(
        ToolCall(name="memory.retrieve", arguments={"query": "info", "scope": "global"}),
        session_id="test",
    )
    assert result.success is True
    assert result.data["count"] == 1
    assert result.data["results"][0]["scope"] == "global"


async def test_memory_retrieve_tool_empty_query(dispatcher: ToolDispatcher) -> None:
    result = await dispatcher.dispatch(
        ToolCall(name="memory.retrieve", arguments={"query": ""}),
        session_id="test",
    )
    assert result.success is True
    assert result.data["count"] == 0
    assert result.data["results"] == []


async def test_memory_retrieve_tool_limit(dispatcher: ToolDispatcher) -> None:
    for i in range(5):
        await dispatcher.dispatch(
            ToolCall(name="memory.store", arguments={"content": f"Item {i}", "scope": "user"}),
            session_id="test",
        )

    result = await dispatcher.dispatch(
        ToolCall(name="memory.retrieve", arguments={"query": "Item", "limit": 3}),
        session_id="test",
    )
    assert result.success is True
    assert result.data["count"] == 3


async def test_memory_delete_tool(dispatcher: ToolDispatcher) -> None:
    store_result = await dispatcher.dispatch(
        ToolCall(name="memory.store", arguments={"content": "To be deleted", "scope": "user"}),
        session_id="test",
    )
    memory_id = store_result.data["id"]

    result = await dispatcher.dispatch(
        ToolCall(name="memory.delete", arguments={"memory_id": memory_id}),
        session_id="test",
    )
    assert result.success is True
    assert result.data["success"] is True
    assert result.data["id"] == memory_id

    # Verify it's gone
    retrieve_result = await dispatcher.dispatch(
        ToolCall(name="memory.retrieve", arguments={"query": "To be deleted"}),
        session_id="test",
    )
    assert retrieve_result.data["count"] == 0


async def test_memory_delete_nonexistent(dispatcher: ToolDispatcher) -> None:
    result = await dispatcher.dispatch(
        ToolCall(name="memory.delete", arguments={"memory_id": "nonexistent-id"}),
        session_id="test",
    )
    assert result.success is False
    assert result.error is not None
    assert "not found" in result.error.lower()


async def test_memory_store_validates_content_length(dispatcher: ToolDispatcher) -> None:
    long_content = "x" * 10001
    result = await dispatcher.dispatch(
        ToolCall(name="memory.store", arguments={"content": long_content}),
        session_id="test",
    )
    assert result.success is False
    assert result.error is not None


async def test_memory_store_validates_confidence(dispatcher: ToolDispatcher) -> None:
    result = await dispatcher.dispatch(
        ToolCall(name="memory.store", arguments={"content": "Test", "confidence": 1.5}),
        session_id="test",
    )
    assert result.success is False


async def test_memory_retrieve_validates_limit(dispatcher: ToolDispatcher) -> None:
    result = await dispatcher.dispatch(
        ToolCall(name="memory.retrieve", arguments={"query": "test", "limit": 0}),
        session_id="test",
    )
    assert result.success is False


async def test_memory_tool_metadata_risk_levels(dispatcher: ToolDispatcher) -> None:
    registry = dispatcher._registry
    store_tool = registry.get("memory.store")
    retrieve_tool = registry.get("memory.retrieve")
    delete_tool = registry.get("memory.delete")

    assert store_tool.metadata.risk_level == RiskLevel.LOW
    assert retrieve_tool.metadata.risk_level == RiskLevel.NONE
    assert delete_tool.metadata.risk_level == RiskLevel.MEDIUM
    assert delete_tool.metadata.requires_confirmation is True
