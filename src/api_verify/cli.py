from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapter import OpenAICompatibleAdapter
from .models import ProviderConfig
from .probes import build_default_probes
from .report import write_markdown
from .scoring import score_records
from .store import JsonlStore, load_jsonl, write_json


def main() -> int:
    parser = argparse.ArgumentParser(prog="api-verify")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run OpenAI-compatible verification probes.")
    run_parser.add_argument("--config", required=True, type=Path)
    run_parser.add_argument("--out", required=True, type=Path)
    run_parser.add_argument("--dry-run", action="store_true")

    report_parser = subparsers.add_parser("report", help="Generate JSON and Markdown reports from runs.jsonl.")
    report_parser.add_argument("--runs", required=True, type=Path)
    report_parser.add_argument("--out", required=True, type=Path)

    args = parser.parse_args()
    if args.command == "run":
        return run_command(args.config, args.out, args.dry_run)
    if args.command == "report":
        return report_command(args.runs, args.out)
    return 2


def run_command(config_path: Path, out_dir: Path, dry_run: bool) -> int:
    config = ProviderConfig.from_json(json.loads(config_path.read_text(encoding="utf-8")))
    adapter = OpenAICompatibleAdapter(config)
    store = JsonlStore(out_dir / "runs.jsonl")
    probes = build_default_probes(config.model, config.sample_count)

    for probe in probes:
        for _ in range(probe.repeats):
            record = adapter.run_probe(probe, dry_run=dry_run)
            store.append(record)
            print(f"{record.probe_id} status={record.status} dry_run={record.dry_run} run_id={record.run_id}")
    return 0


def report_command(runs_path: Path, out_dir: Path) -> int:
    records = load_jsonl(runs_path)
    report = score_records(records)
    write_json(out_dir / "report.json", report)
    write_markdown(out_dir / "report.md", report)
    print(f"verdict={report['verdict']} score={report['overall_score']} report={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
