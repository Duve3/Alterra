import pytest

from alterra.memory import (
    MemoryCreate,
    MemoryRetriever,
    MemoryScope,
    MemorySource,
    SQLiteMemoryStore,
)


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "memory" / "alterra.db"


async def test_store_persists_full_memory_record_across_instances(database_path) -> None:
    store = SQLiteMemoryStore(database_path)
    created = await store.create(
        MemoryCreate(
            content="Prefers dark mode",
            source=MemorySource.USER,
            scope=MemoryScope.USER,
            scope_id="alex",
            confidence=0.9,
            created_by="alex",
            metadata={"category": "preference"},
        )
    )
    reloaded = await SQLiteMemoryStore(database_path).get(created.id)
    assert reloaded == created
    assert database_path.exists()


async def test_search_filters_scope_scope_id_and_limit(database_path) -> None:
    store = SQLiteMemoryStore(database_path)
    await store.create(MemoryCreate(content="Alice likes tea", scope_id="alice"))
    await store.create(MemoryCreate(content="Alice likes coffee", scope_id="alice"))
    await store.create(MemoryCreate(content="Bob likes tea", scope_id="bob"))
    matches = await store.search("LIKES", scope=MemoryScope.USER, scope_id="alice", limit=1)
    assert len(matches) == 1
    assert matches[0].scope_id == "alice"
    assert await store.search("  ") == []


async def test_retriever_delegates_and_store_handles_missing_and_delete(database_path) -> None:
    store = SQLiteMemoryStore(database_path)
    created = await store.create(MemoryCreate(content="Team meets Tuesdays"))
    assert [item.id for item in await MemoryRetriever(store).retrieve("tuesdays")] == [created.id]
    assert await store.delete(created.id) is True
    assert await store.get(created.id) is None
    assert await store.delete(created.id) is False


async def test_search_rejects_invalid_limit(database_path) -> None:
    with pytest.raises(ValueError, match="at least one"):
        await SQLiteMemoryStore(database_path).search("anything", limit=0)


async def test_store_initializes_once_when_operations_are_concurrent(database_path) -> None:
    store = SQLiteMemoryStore(database_path)
    records = await __import__("asyncio").gather(*[store.create(MemoryCreate(content=str(number))) for number in range(2)])
    assert len(records) == 2
