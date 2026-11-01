"""Tests for filesystem integration tools."""

import tempfile
from pathlib import Path
import pytest

from alterra.core.messages import ToolCall
from alterra.tools.dispatcher import ToolDispatcher
from alterra.tools.registry import ToolRegistry
from alterra.integrations.filesystem import (
    ReadFileTool,
    WriteFileTool,
    ListFilesTool,
    SearchFilesTool,
)


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = tempfile.gettempdir()
        import os
        os.chdir(tmpdir)
        yield Path(tmpdir)
        os.chdir(old_cwd)


@pytest.fixture
def dispatcher(temp_workspace):
    registry = ToolRegistry()
    for tool in (ReadFileTool(), WriteFileTool(), ListFilesTool(), SearchFilesTool()):
        registry.register(tool)
    return ToolDispatcher(registry)


async def test_write_and_read_file(dispatcher: ToolDispatcher, temp_workspace):
    # Write a file
    result = await dispatcher.dispatch(
        ToolCall(name="filesystem.write", arguments={"path": "test.txt", "content": "Hello World"}),
        session_id="test",
    )
    assert result.success is True
    assert result.data["bytes_written"] == 11

    # Read it back
    result = await dispatcher.dispatch(
        ToolCall(name="filesystem.read", arguments={"path": "test.txt"}),
        session_id="test",
    )
    assert result.success is True
    assert result.data["content"] == "Hello World"


async def test_read_nonexistent_file(dispatcher: ToolDispatcher, temp_workspace):
    result = await dispatcher.dispatch(
        ToolCall(name="filesystem.read", arguments={"path": "nonexistent.txt"}),
        session_id="test",
    )
    assert result.success is False
    assert "not found" in result.error.lower()


async def test_write_creates_parent_dirs(dispatcher: ToolDispatcher, temp_workspace):
    result = await dispatcher.dispatch(
        ToolCall(name="filesystem.write", arguments={"path": "subdir/nested.txt", "content": "nested"}),
        session_id="test",
    )
    assert result.success is True

    result = await dispatcher.dispatch(
        ToolCall(name="filesystem.read", arguments={"path": "subdir/nested.txt"}),
        session_id="test",
    )
    assert result.data["content"] == "nested"


async def test_list_files(dispatcher: ToolDispatcher, temp_workspace):
    # Create some test files
    (temp_workspace / "file1.txt").write_text("a")
    (temp_workspace / "file2.py").write_text("b")
    (temp_workspace / "subdir").mkdir()
    (temp_workspace / "subdir" / "file3.txt").write_text("c")

    result = await dispatcher.dispatch(
        ToolCall(name="filesystem.list", arguments={"path": ".", "recursive": True}),
        session_id="test",
    )
    assert result.success is True
    assert result.data["count"] >= 3
    names = {e["name"] for e in result.data["entries"]}
    assert "file1.txt" in names
    assert "file2.py" in names


async def test_list_with_pattern(dispatcher: ToolDispatcher, temp_workspace):
    (temp_workspace / "test.py").write_text("a")
    (temp_workspace / "test.txt").write_text("b")
    (temp_workspace / "other.py").write_text("c")

    result = await dispatcher.dispatch(
        ToolCall(name="filesystem.list", arguments={"path": ".", "pattern": "test.*"}),
        session_id="test",
    )
    assert result.success is True
    assert result.data["count"] == 2


async def test_search_files(dispatcher: ToolDispatcher, temp_workspace):
    (temp_workspace / "main.py").write_text("def hello():\n    print('hello world')\n")
    (temp_workspace / "utils.py").write_text("def helper():\n    return 42\n")
    (temp_workspace / "readme.txt").write_text("This is a hello world example")

    result = await dispatcher.dispatch(
        ToolCall(name="filesystem.search", arguments={"pattern": "hello", "path": "."}),
        session_id="test",
    )
    assert result.success is True
    assert result.data["count"] >= 1
    paths = {r["path"] for r in result.data["results"]}
    assert "main.py" in paths or "readme.txt" in paths


async def test_search_case_sensitive(dispatcher: ToolDispatcher, temp_workspace):
    (temp_workspace / "test.py").write_text("HELLO world\nhello WORLD")

    result = await dispatcher.dispatch(
        ToolCall(name="filesystem.search", arguments={"pattern": "HELLO", "path": ".", "case_sensitive": True}),
        session_id="test",
    )
    assert result.success is True
    assert result.data["count"] == 1
    assert "HELLO" in result.data["results"][0]["matches"][0]["context"][0]


async def test_search_with_file_pattern(dispatcher: ToolDispatcher, temp_workspace):
    (temp_workspace / "code.py").write_text("import os")
    (temp_workspace / "note.txt").write_text("import os")

    result = await dispatcher.dispatch(
        ToolCall(name="filesystem.search", arguments={"pattern": "import", "path": ".", "file_pattern": "*.py"}),
        session_id="test",
    )
    assert result.success is True
    assert result.data["count"] == 1
    assert result.data["results"][0]["path"] == "code.py"