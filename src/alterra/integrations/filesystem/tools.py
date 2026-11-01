"""File system tools - real capabilities, not demos."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ...tools.base import Tool, ToolContext

# --- Read File ---

class ReadFileArgs(BaseModel):
    path: str = Field(description="File path to read (relative to workspace root)")
    encoding: str = Field(default="utf-8", description="Text encoding")


class ReadFileTool(Tool):
    name = "filesystem.read"
    description = "Read the contents of a text file"
    arguments_model = ReadFileArgs
    timeout_seconds = 10.0

    async def execute(self, arguments: BaseModel, context: ToolContext) -> Any:
        args = arguments  # type: ReadFileArgs
        path = Path(args.path).resolve()

        # Safety: restrict to workspace
        workspace = Path.cwd().resolve()
        if not path.is_relative_to(workspace):
            raise ValueError(f"Path must be within workspace: {workspace}")

        if not path.exists():
            raise ValueError(f"File not found: {args.path}")
        if not path.is_file():
            raise ValueError(f"Not a file: {args.path}")

        content = path.read_text(encoding=args.encoding)
        return {"path": str(path), "content": content, "size": len(content)}


# --- Write File ---

class WriteFileArgs(BaseModel):
    path: str = Field(description="File path to write (relative to workspace root)")
    content: str = Field(description="Content to write")
    encoding: str = Field(default="utf-8", description="Text encoding")
    create_dirs: bool = Field(default=True, description="Create parent directories if needed")


class WriteFileTool(Tool):
    name = "filesystem.write"
    description = "Write content to a file (creates or overwrites)"
    arguments_model = WriteFileArgs
    timeout_seconds = 10.0

    async def execute(self, arguments: BaseModel, context: ToolContext) -> Any:
        args = arguments  # type: WriteFileArgs
        path = Path(args.path).resolve()

        workspace = Path.cwd().resolve()
        if not path.is_relative_to(workspace):
            raise ValueError(f"Path must be within workspace: {workspace}")

        if args.create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(args.content, encoding=args.encoding)
        return {"path": str(path), "bytes_written": len(args.content.encode(args.encoding))}


# --- List Files ---

class ListFilesArgs(BaseModel):
    path: str = Field(default=".", description="Directory path to list")
    recursive: bool = Field(default=False, description="List recursively")
    pattern: str | None = Field(default=None, description="Glob pattern filter (e.g., '*.py')")


class ListFilesTool(Tool):
    name = "filesystem.list"
    description = "List files and directories"
    arguments_model = ListFilesArgs
    timeout_seconds = 10.0

    async def execute(self, arguments: BaseModel, context: ToolContext) -> Any:
        args = arguments  # type: ListFilesArgs
        path = Path(args.path).resolve()

        workspace = Path.cwd().resolve()
        if not path.is_relative_to(workspace):
            raise ValueError(f"Path must be within workspace: {workspace}")

        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {args.path}")
        if not path.is_dir():
            raise ValueError(f"Not a directory: {args.path}")

        if args.recursive:
            entries = path.rglob("*")
        else:
            entries = path.iterdir()

        if args.pattern:
            entries = (e for e in entries if fnmatch.fnmatch(e.name, args.pattern))

        results = []
        for entry in sorted(entries):
            try:
                stat = entry.stat()
                results.append({
                    "path": str(entry.relative_to(workspace)),
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size": stat.st_size if entry.is_file() else None,
                    "modified": stat.st_mtime,
                })
            except (OSError, PermissionError):
                continue

        return {"path": str(path.relative_to(workspace)), "entries": results, "count": len(results)}


# --- Search Files (grep-like) ---

class SearchFilesArgs(BaseModel):
    pattern: str = Field(description="Text pattern to search for")
    path: str = Field(default=".", description="Directory to search in")
    file_pattern: str | None = Field(default=None, description="File glob pattern (e.g., '*.py')")
    case_sensitive: bool = Field(default=False, description="Case sensitive search")
    max_results: int = Field(default=50, ge=1, le=500, description="Max results to return")


class SearchFilesTool(Tool):
    name = "filesystem.search"
    description = "Search for text pattern in files (grep-like)"
    arguments_model = SearchFilesArgs
    timeout_seconds = 30.0

    async def execute(self, arguments: BaseModel, context: ToolContext) -> Any:
        args = arguments  # type: SearchFilesArgs
        path = Path(args.path).resolve()

        workspace = Path.cwd().resolve()
        if not path.is_relative_to(workspace):
            raise ValueError(f"Path must be within workspace: {workspace}")

        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {args.path}")

        # Find files to search
        if args.file_pattern:
            files = path.rglob(args.file_pattern) if "**" in args.file_pattern or args.path != "." else path.glob(args.file_pattern)
        else:
            files = path.rglob("*")

        files = [f for f in files if f.is_file()]

        search_pattern = args.pattern if args.case_sensitive else args.pattern.lower()
        results = []

        for file_path in files:
            if len(results) >= args.max_results:
                break
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                search_content = content if args.case_sensitive else content.lower()

                if search_pattern in search_content:
                    # Find matching lines with context
                    lines = content.splitlines()
                    matches = []
                    for i, line in enumerate(lines):
                        check_line = line if args.case_sensitive else line.lower()
                        if search_pattern in check_line:
                            start = max(0, i - 1)
                            end = min(len(lines), i + 2)
                            matches.append({
                                "line_number": i + 1,
                                "context": lines[start:end],
                            })

                    if matches:
                        rel_path = file_path.relative_to(workspace)
                        results.append({
                            "path": str(rel_path),
                            "matches": matches[:5],  # Limit context per file
                        })
            except (OSError, PermissionError, UnicodeDecodeError):
                continue

        return {"pattern": args.pattern, "path": str(path.relative_to(workspace)), "results": results, "count": len(results)}