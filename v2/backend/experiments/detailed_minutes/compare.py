# /// script
# requires-python = ">=3.11"
# ///
"""Compare evaluated runs side by side.

Usage:
    uv run compare.py              # every run under runs/ that has eval/
    uv run compare.py runs/a runs/b

Columns: QA = question-answering score from the minutes (transcript ceiling in
brackets); size = minutes tokens as a share of transcript tokens; wrong =
answers contradicting the reference; grounded = sampled minutes bullets the
transcript supports; in/out = LLM tokens spent generating the minutes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def summarize(run: Path) -> dict | None:
    evals = [json.loads(p.read_text()) for p in sorted((run / "eval").glob("*-*.json"))]
    if not evals:
        return None
    metas = {e["id"]: json.loads((run / f"{e['id']}.json").read_text()) for e in evals}
    settings = json.loads((run / "settings.json").read_text())
    q = sum(e["questions"] for e in evals)

    def qa(src: str) -> float:
        return sum(e["sources"][src]["score"] * e["questions"] for e in evals) / q

    per_rec = {e["id"][:8]: round(e["sources"]["minutes"]["score"], 2) for e in evals}
    sampled = sum(e["grounding"]["sampled"] for e in evals)
    return {
        "run": run.name,
        "chunk": f"{settings['chunk_tokens']} tok" if settings.get("chunk_tokens")
                 else f"{settings['chunk_minutes']:g} min",
        "prompt": settings["prompts"][0] + (f" r{settings['target_ratio']:g}" if settings.get("target_ratio") else ""),
        "qa": qa("minutes"),
        "ceiling": qa("transcript"),
        "size": sum(m["minutes_tokens"] for m in metas.values()) / sum(m["transcript_tokens"] for m in metas.values()),
        "minutes_tok": sum(m["minutes_tokens"] for m in metas.values()),
        "wrong": sum(e["sources"]["minutes"]["counts"]["wrong"] for e in evals),
        "grounded": sum(e["grounding"]["counts"]["supported"] for e in evals) / max(sampled, 1),
        "sampled": sampled,
        "in": sum(m["prompt_tokens"] for m in metas.values()),
        "out": sum(m["completion_tokens"] for m in metas.values()),
        "reasoning": sum(m["reasoning_tokens"] for m in metas.values()),
        "effort": settings.get("effort"),
        "calls": sum(len(m["calls"]) for m in metas.values()),
        "n": len(evals),
        "per_rec": per_rec,
    }


def main() -> None:
    runs = [Path(a) for a in sys.argv[1:]] or sorted(p.parent for p in (HERE / "runs").glob("*/eval"))
    rows = [r for r in (summarize(p) for p in runs) if r]
    rows.sort(key=lambda r: (r["prompt"], r["chunk"]))
    print("| Prompt | Chunk | Effort | QA (ceiling) | Size vs transcript | Minutes tok | Wrong | Grounded | Gen in / out (reasoning) tok | Calls |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['prompt']} | {r['chunk']} | {r['effort']} | {r['qa']:.0%} ({r['ceiling']:.0%}) | {r['size']:.0%} | "
              f"{r['minutes_tok']:,} | {r['wrong']} | {r['grounded']:.0%} | "
              f"{r['in'] / 1000:.0f}k / {r['out'] / 1000:.0f}k ({r['reasoning'] / 1000:.0f}k) | {r['calls']} |")
    ids = sorted({k for r in rows for k in r["per_rec"]})
    print("\nPer-recording minutes QA:\n")
    print("| Prompt | Chunk | " + " | ".join(ids) + " |")
    print("|---|---|" + "---|" * len(ids))
    for r in rows:
        print(f"| {r['prompt']} | {r['chunk']} | " + " | ".join(f"{r['per_rec'].get(i, '—')}" for i in ids) + " |")


if __name__ == "__main__":
    main()
