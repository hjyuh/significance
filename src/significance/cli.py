from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from significance.diff import diff_records, format_diff_human
from significance.init import scaffold_record, write_record
from significance.records import load_record, validator
from significance.validate import validate_paths


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="significance")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="interactively scaffold a new record")
    p_init.add_argument("--records-dir", default="records")

    p_validate = sub.add_parser("validate", help="validate one or more records")
    p_validate.add_argument("paths", nargs="+", help="record file(s) or a directory of *.yaml records")
    p_validate.add_argument(
        "--base", help="git ref or file path to compare against for append-only enforcement"
    )
    p_validate.add_argument("--json", action="store_true")

    p_diff = sub.add_parser("diff", help="human-readable semantic diff between two record files")
    p_diff.add_argument("a")
    p_diff.add_argument("b")
    p_diff.add_argument("--json", action="store_true")

    return parser


def _cmd_init(args) -> int:
    record = scaffold_record(input)
    errors = list(validator().iter_errors(record))
    for e in errors:
        print(f"warning: {e.message}", file=sys.stderr)
    path = write_record(record, Path(args.records_dir))
    print(f"Wrote {path}")
    return 0


def _cmd_validate(args) -> int:
    violations = validate_paths(args.paths, base=args.base)
    if args.json:
        print(json.dumps([v.to_dict() for v in violations], indent=2))
    elif violations:
        for v in violations:
            print(str(v))
    else:
        print("OK: no violations.")
    return 1 if violations else 0


def _cmd_diff(args) -> int:
    a = load_record(args.a)
    b = load_record(args.b)
    result = diff_records(a, b)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(format_diff_human(result))
    return 1 if result["append_only_violations"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    handlers = {"init": _cmd_init, "validate": _cmd_validate, "diff": _cmd_diff}
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
