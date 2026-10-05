from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("wail-multi-agent-example")

REPO_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "node_modules",
    "site-packages",
    "venv",
}
MAX_FILE_BYTES = 512_000
MAX_SEARCH_RESULTS = 50
MAX_READ_LINES = 240


def _python_files() -> list[Path]:
    files: list[Path] = []

    for path in REPO_ROOT.rglob("*.py"):
        if not path.is_file():
            continue

        relative = path.relative_to(REPO_ROOT)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue

        files.append(path)

    return sorted(files, key=lambda item: item.as_posix())


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _resolve_repo_python_file(relative_path: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("path is required")

    candidate = (REPO_ROOT / relative_path).resolve()

    try:
        candidate.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ValueError("path must remain inside the repository") from exc

    if candidate.suffix.lower() != ".py":
        raise ValueError("only Python source files are allowed")

    if not candidate.is_file():
        raise FileNotFoundError(relative_path)

    relative = candidate.relative_to(REPO_ROOT)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        raise ValueError("path points to an excluded directory")

    if candidate.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("file exceeds example read limit")

    return candidate


def _read_lines(path: Path) -> list[str]:
    return path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()


@mcp.tool()
def list_python_files(
    path_prefix: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """List real Python source files in the current WAIL repository."""
    safe_limit = max(1, min(int(limit), 500))
    prefix = path_prefix.replace("\\", "/").strip("/")

    matches: list[dict[str, Any]] = []

    for path in _python_files():
        relative = _relative(path)

        if prefix and not relative.startswith(prefix):
            continue

        stat = path.stat()
        matches.append(
            {
                "path": relative,
                "size_bytes": stat.st_size,
            }
        )

        if len(matches) >= safe_limit:
            break

    return {
        "repository": REPO_ROOT.name,
        "path_prefix": prefix or None,
        "count": len(matches),
        "files": matches,
    }


@mcp.tool()
def inspect_python_file(
    path: str,
) -> dict[str, Any]:
    """Inspect a real Python file and return structural source information."""
    source_path = _resolve_repo_python_file(path)
    source = source_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {
            "path": _relative(source_path),
            "syntax_valid": False,
            "syntax_error": {
                "line": exc.lineno,
                "offset": exc.offset,
                "message": exc.msg,
            },
        }

    functions: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "async": isinstance(node, ast.AsyncFunctionDef),
                }
            )
        elif isinstance(node, ast.ClassDef):
            classes.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                }
            )
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append(module)

    lines = source.splitlines()

    return {
        "path": _relative(source_path),
        "syntax_valid": True,
        "size_bytes": source_path.stat().st_size,
        "line_count": len(lines),
        "function_count": len(functions),
        "class_count": len(classes),
        "functions": sorted(functions, key=lambda item: item["line"])[:100],
        "classes": sorted(classes, key=lambda item: item["line"])[:100],
        "imports": sorted(set(item for item in imports if item))[:100],
    }


@mcp.tool()
def read_python_source(
    path: str,
    start_line: int = 1,
    end_line: int = 120,
) -> dict[str, Any]:
    """Read a bounded line range from a real Python source file."""
    source_path = _resolve_repo_python_file(path)
    lines = _read_lines(source_path)

    start = max(1, int(start_line))
    end = max(start, int(end_line))
    end = min(end, start + MAX_READ_LINES - 1, len(lines))

    selected = [
        {
            "line": index,
            "text": lines[index - 1],
        }
        for index in range(start, end + 1)
    ]

    return {
        "path": _relative(source_path),
        "start_line": start,
        "end_line": end,
        "total_lines": len(lines),
        "lines": selected,
    }


@mcp.tool()
def search_python_source(
    query: str,
    path_prefix: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """Search literal text across real Python files in the WAIL repository."""
    if not isinstance(query, str) or not query:
        raise ValueError("query is required")

    safe_limit = max(1, min(int(limit), MAX_SEARCH_RESULTS))
    prefix = path_prefix.replace("\\", "/").strip("/")
    needle = query.casefold()

    matches: list[dict[str, Any]] = []

    for source_path in _python_files():
        relative = _relative(source_path)

        if prefix and not relative.startswith(prefix):
            continue

        if source_path.stat().st_size > MAX_FILE_BYTES:
            continue

        lines = _read_lines(source_path)

        for line_number, line in enumerate(lines, start=1):
            if needle not in line.casefold():
                continue

            matches.append(
                {
                    "path": relative,
                    "line": line_number,
                    "text": line.strip(),
                }
            )

            if len(matches) >= safe_limit:
                return {
                    "query": query,
                    "path_prefix": prefix or None,
                    "count": len(matches),
                    "matches": matches,
                    "truncated": True,
                }

    return {
        "query": query,
        "path_prefix": prefix or None,
        "count": len(matches),
        "matches": matches,
        "truncated": False,
    }


@mcp.tool()
def python_file_stats(
    path_prefix: str = "",
    top_n: int = 10,
) -> dict[str, Any]:
    """Return real repository Python file counts and largest files."""
    prefix = path_prefix.replace("\\", "/").strip("/")
    safe_top_n = max(1, min(int(top_n), 50))

    records: list[dict[str, Any]] = []
    total_bytes = 0
    total_lines = 0

    for source_path in _python_files():
        relative = _relative(source_path)

        if prefix and not relative.startswith(prefix):
            continue

        stat = source_path.stat()
        line_count = len(_read_lines(source_path))

        total_bytes += stat.st_size
        total_lines += line_count

        records.append(
            {
                "path": relative,
                "size_bytes": stat.st_size,
                "line_count": line_count,
            }
        )

    largest = sorted(
        records,
        key=lambda item: (
            item["size_bytes"],
            item["line_count"],
            item["path"],
        ),
        reverse=True,
    )[:safe_top_n]

    return {
        "repository": REPO_ROOT.name,
        "path_prefix": prefix or None,
        "python_file_count": len(records),
        "total_size_bytes": total_bytes,
        "total_line_count": total_lines,
        "largest_files": largest,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
