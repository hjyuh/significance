"""Runs host-side, after the sandboxed build container has exited, to turn
what the untrusted-build workflow observed into isolation-evidence.json
plus build-receipt.json / axiom-execution.json.

This script is part of the *untrusted* workflow (it runs in the same job,
still with no write tokens and no secrets) -- the fail-closed decision
itself is made later, trusted-side, by isolation.check_isolation() reading
the isolation-evidence.json this script writes. This script's only job is
honest bookkeeping: report exactly what was observed, never round up to
"clean" when something is ambiguous.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import json

_EROFS_RE = re.compile(r"Read-only file system[^\n]*", re.IGNORECASE)
_NETWORK_ERROR_RE = re.compile(
    r"(Could not resolve host|Network is unreachable|Connection timed out|"
    r"Temporary failure in name resolution)[^\n]*",
    re.IGNORECASE,
)


def _sha256(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _parse_env_file(path: Path) -> dict:
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip()
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exit-code", required=True, type=int)
    parser.add_argument("--terminated-by-timeout", required=True)
    parser.add_argument("--disk-violation", required=True)
    parser.add_argument("--wall-clock-limit", required=True, type=int)
    parser.add_argument("--build-log", required=True)
    parser.add_argument("--build-result-env", required=True)
    parser.add_argument("--sandbox-digest", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    build_log = Path(args.build_log)
    out_dir = Path(args.out_dir)
    log_text = build_log.read_text(encoding="utf-8", errors="replace") if build_log.exists() else ""

    terminated_by_timeout = args.terminated_by_timeout.strip().lower() == "true"
    disk_violation = args.disk_violation.strip().lower() == "true"

    unauthorized_writes = sorted(set(_EROFS_RE.findall(log_text)))
    network_attempts = len(_NETWORK_ERROR_RE.findall(log_text))

    isolation_evidence = {
        "runner": "github-hosted-ephemeral",
        "secrets_in_scope": False,
        "network": {
            "denied_after_acquisition": True,  # structural: --network none
            "egress_attempts_after_denial": network_attempts,
        },
        "resource_limits": {
            "cpu_enforced": True,   # structural: --cpus
            "memory_enforced": True,  # structural: --memory
            "pids_enforced": True,  # structural: --pids-limit
            "disk_enforced": not disk_violation,
        },
        "wall_clock": {
            "enforced": True,
            "limit_seconds": args.wall_clock_limit,
            "terminated_by_timeout": terminated_by_timeout,
        },
        "filesystem": {
            "read_only_except": ["/workspace/build-out"],
            "unauthorized_write_attempts": unauthorized_writes,
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "isolation-evidence.json").write_text(
        json.dumps(isolation_evidence, indent=2), encoding="utf-8"
    )

    env_values = _parse_env_file(Path(args.build_result_env))
    build_result = env_values.get("build_result", "failed")
    axiom_result = env_values.get("axiom_result", "failed")
    if terminated_by_timeout or disk_violation:
        build_result = "failed"
        axiom_result = "failed"

    common = {
        "tool": "significance-lean",
        "tool_version": "0.1.0",
        "runner_image_digest": args.sandbox_digest,
        "executed_at": env_values.get("executed_at", "1970-01-01T00:00:00Z"),
        "log_sha256": _sha256(build_log),
        "asserted_by": "significance-ci",
    }
    (out_dir / "build-receipt.json").write_text(
        json.dumps({**common, "result": build_result}, indent=2), encoding="utf-8"
    )
    (out_dir / "axiom-execution.json").write_text(
        json.dumps({**common, "result": axiom_result}, indent=2), encoding="utf-8"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
