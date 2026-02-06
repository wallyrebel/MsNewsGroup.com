from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .audit import AuditError, audit_site, summarize_for_terminal
from .reporting import build_report_payload, render_markdown


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_audit(args: argparse.Namespace) -> int:
    audit = audit_site(args.site, sample_size=args.sample_size)
    print(summarize_for_terminal(audit))

    if args.json_out:
        _write_json(Path(args.json_out), audit)
        print(f"\nSaved audit JSON: {args.json_out}")

    return 0


def _run_report(args: argparse.Namespace) -> int:
    audit = audit_site(args.site, sample_size=args.sample_size)
    payload = build_report_payload(audit)
    markdown = render_markdown(audit, payload["issues"])

    _write_text(Path(args.markdown_out), markdown)
    _write_json(Path(args.json_out), payload)

    print(summarize_for_terminal(audit))
    print(f"\nSaved markdown report: {args.markdown_out}")
    print(f"Saved JSON summary: {args.json_out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wp_news_ops",
        description="Audit WordPress news visibility signals and generate a remediation report.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_cmd = subparsers.add_parser("audit", help="Run audit checks and print results.")
    audit_cmd.add_argument("--site", required=True, help="Site URL, e.g. https://msnewsgroup.com/")
    audit_cmd.add_argument("--sample-size", type=int, default=10, help="Number of articles to sample.")
    audit_cmd.add_argument("--json-out", help="Optional JSON output path.")
    audit_cmd.set_defaults(handler=_run_audit)

    report_cmd = subparsers.add_parser("report", help="Run audit and write markdown/json report outputs.")
    report_cmd.add_argument("--site", required=True, help="Site URL, e.g. https://msnewsgroup.com/")
    report_cmd.add_argument("--sample-size", type=int, default=10, help="Number of articles to sample.")
    report_cmd.add_argument(
        "--markdown-out",
        default="reports/latest.md",
        help="Path to write markdown report.",
    )
    report_cmd.add_argument(
        "--json-out",
        default="reports/latest.json",
        help="Path to write JSON report payload.",
    )
    report_cmd.set_defaults(handler=_run_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.handler(args))
    except AuditError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
