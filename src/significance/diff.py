"""`significance diff a.yaml b.yaml`: a human-readable semantic diff from a
(base) to b (current), calling out freshness/staleness transitions and any
append-only violation (b is checked against a as its base).
"""

from __future__ import annotations

from significance.pathfmt import format_path
from significance.semantics import check_append_only

_MISSING = object()


def _diff(a, b, path=()):
    if isinstance(a, dict) and isinstance(b, dict):
        changes = []
        for key in sorted(set(a) | set(b), key=str):
            av = a.get(key, _MISSING)
            bv = b.get(key, _MISSING)
            if av is _MISSING:
                changes.append({"path": path + (key,), "kind": "added", "old": None, "new": bv})
            elif bv is _MISSING:
                changes.append({"path": path + (key,), "kind": "removed", "old": av, "new": None})
            else:
                changes.extend(_diff(av, bv, path + (key,)))
        return changes

    if isinstance(a, list) and isinstance(b, list):
        keyed_a = a and all(isinstance(x, dict) and "id" in x for x in a)
        keyed_b = b and all(isinstance(x, dict) and "id" in x for x in b)
        if keyed_a and keyed_b:
            a_map = {x["id"]: x for x in a}
            b_map = {x["id"]: x for x in b}
            changes = []
            for id_ in sorted(set(a_map) | set(b_map), key=str):
                sub_path = path + (f"id={id_}",)
                if id_ not in a_map:
                    changes.append(
                        {"path": sub_path, "kind": "added", "old": None, "new": b_map[id_]}
                    )
                elif id_ not in b_map:
                    changes.append(
                        {"path": sub_path, "kind": "removed", "old": a_map[id_], "new": None}
                    )
                else:
                    changes.extend(_diff(a_map[id_], b_map[id_], sub_path))
            return changes

        changes = []
        for i in range(max(len(a), len(b))):
            sub_path = path + (i,)
            if i >= len(a):
                changes.append({"path": sub_path, "kind": "added", "old": None, "new": b[i]})
            elif i >= len(b):
                changes.append({"path": sub_path, "kind": "removed", "old": a[i], "new": None})
            else:
                changes.extend(_diff(a[i], b[i], sub_path))
        return changes

    if a != b:
        return [{"path": path, "kind": "changed", "old": a, "new": b}]
    return []


def diff_records(a: dict, b: dict) -> dict:
    changes = _diff(a, b)
    for c in changes:
        c["path"] = format_path(c["path"])

    append_only_violations = check_append_only(current=b, base=a)

    staleness_transition = None
    a_result = (a.get("freshness") or {}).get("result")
    b_result = (b.get("freshness") or {}).get("result")
    if a_result != b_result:
        staleness_transition = {"from": a_result, "to": b_result}

    return {
        "changes": changes,
        "staleness_transition": staleness_transition,
        "append_only_violations": [v.to_dict() for v in append_only_violations],
    }


def format_diff_human(result: dict) -> str:
    lines: list[str] = []

    if result["staleness_transition"]:
        t = result["staleness_transition"]
        lines.append(f"FRESHNESS TRANSITION: {t['from']!r} -> {t['to']!r}")

    if result["append_only_violations"]:
        lines.append("APPEND-ONLY VIOLATIONS:")
        for v in result["append_only_violations"]:
            lines.append(f"  [{v['rule']}] {v['location']}: {v['message']}")

    if result["changes"]:
        lines.append("CHANGES:")
        for c in result["changes"]:
            if c["kind"] == "added":
                lines.append(f"  + {c['path']}: {c['new']!r}")
            elif c["kind"] == "removed":
                lines.append(f"  - {c['path']}: {c['old']!r}")
            else:
                lines.append(f"  ~ {c['path']}: {c['old']!r} -> {c['new']!r}")

    if not lines:
        lines.append("No differences.")

    return "\n".join(lines)
