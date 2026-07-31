"""Shared dotted/bracket path formatting, e.g. evidence[0].correspondence.basis."""

from __future__ import annotations


def format_path(path) -> str:
    parts: list[str] = []
    for p in path:
        is_bracketed = isinstance(p, int) or (isinstance(p, str) and p.startswith("id="))
        if is_bracketed:
            if parts:
                parts[-1] += f"[{p}]"
            else:
                parts.append(f"[{p}]")
        else:
            parts.append(str(p))
    return ".".join(parts) if parts else "$"


def walk(node, path: tuple = ()):
    """Yield (path_tuple, node) for every dict/list node, depth-first, including the root."""
    yield path, node
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, path + (k,))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from walk(item, path + (i,))
