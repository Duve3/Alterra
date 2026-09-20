import pytest
from pydantic import ValidationError

from alterra.memory import MemoryCreate, MemoryScope, MemorySource


def test_memory_create_normalizes_and_defaults_provenance() -> None:
    memory = MemoryCreate(content="  Likes robotics  ")
    assert memory.content == "Likes robotics"
    assert memory.source is MemorySource.USER
    assert memory.scope is MemoryScope.USER
    assert memory.created_by == "user"


@pytest.mark.parametrize("content", ["", "   "])
def test_memory_rejects_empty_content(content: str) -> None:
    with pytest.raises(ValidationError):
        MemoryCreate(content=content)
