"""Tests for memory models."""

import pytest

from alterra.memory.models import MemoryCreate, MemoryScope, MemorySource


def test_memory_create_normalizes_and_defaults_provenance() -> None:
    mem = MemoryCreate(content="User likes coffee")
    assert mem.content == "User likes coffee"
    assert mem.source == MemorySource.USER
    assert mem.scope == MemoryScope.USER
    assert mem.confidence == 1.0
    assert mem.created_by == "user"
    assert mem.metadata == {}


def test_memory_create_accepts_explicit_values() -> None:
    mem = MemoryCreate(
        content="Explicit fact",
        source=MemorySource.ASSISTANT,
        scope=MemoryScope.GLOBAL,
        scope_id="global-1",
        confidence=0.8,
        created_by="test-agent",
        metadata={"tags": ["preference"]},
    )
    assert mem.source == MemorySource.ASSISTANT
    assert mem.scope == MemoryScope.GLOBAL
    assert mem.scope_id == "global-1"
    assert mem.confidence == 0.8
    assert mem.created_by == "test-agent"
    assert mem.metadata == {"tags": ["preference"]}


@pytest.mark.parametrize("bad_content", ["", "   "])
def test_memory_rejects_empty_content(bad_content: str) -> None:
    with pytest.raises(ValueError):
        MemoryCreate(content=bad_content)
