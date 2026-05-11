from __future__ import annotations

from pathlib import Path
from typing import Any


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# API Relay Verification Report",
        "",
        f"Overall verdict: **{report['verdict']}**",
        f"Overall score: **{report['overall_score']} / 100**",
        "",
        "## Interpretation Boundary",
        "",
        report["field_forgery_warning"],
        "",
        "本报告是证据型风险评分，不是数学证明。行为证据、错误语义和重复样本比单个返回字段更有价值。",
        "",
        "## Dimension Scores",
        "",
        "| Dimension | Score | Runs |",
        "| --- | ---: | ---: |",
    ]
    for dimension, item in report["dimensions"].items():
        lines.append(f"| {dimension} | {item['score']} | {item['runs']} |")

    lines.extend(["", "## Evidence", ""])
    for item in report["evidence"]:
        lines.extend(
            [
                f"### {item['probe_id']} ({item['category']})",
                "",
                f"- Verdict: {item['verdict']}",
                f"- Score: {item['score']} / 100",
                f"- Artifact: `{item['artifact_ref']}`",
                f"- Rationale: {item['rationale']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report), encoding="utf-8")
