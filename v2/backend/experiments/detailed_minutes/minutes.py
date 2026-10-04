# /// script
# requires-python = ">=3.11"
# dependencies = ["openai", "python-dotenv", "tiktoken"]
# ///
"""Generate detailed minutes for cached recordings, one time-window at a time.

Each chunk call sees: the meeting header, the minutes written so far
(read-only), the last few minutes of transcript before the chunk (read-only),
and the new chunk. It writes minutes for the new chunk only. A final call
writes the overview (gist, decisions, actions, open questions) from the
minutes alone.

Usage:
    uv run minutes.py --all                         # every cached recording
    uv run minutes.py <id> [<id> ...] --chunk-minutes 5 --coverage --run c5-cov
    uv run minutes.py --all --model gpt-5-mini --effort low

Output: runs/<run>/<id>.md and <id>.json (settings, token usage, timings).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import tiktoken
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI, RateLimitError

HERE = Path(__file__).resolve().parent
REC_DIR = HERE / "cache" / "recordings"
RUNS = HERE / "runs"
PROMPTS = HERE / "prompts"
load_dotenv(HERE / ".env")

ENC = tiktoken.get_encoding("o200k_base")

# Consecutive phrases by one speaker are merged into a turn unless there is a
# long pause or the turn gets long, so timestamps stay reasonably fine-grained.
TURN_MAX_GAP_MS = 4_000
TURN_MAX_LEN_MS = 60_000


def ntok(text: str) -> int:
    return len(ENC.encode(text or ""))


def ts(ms: int) -> str:
    s = ms // 1000
    h, m, s = s // 3600, s // 60 % 60, s % 60
    return f"{h}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"


@dataclass
class Turn:
    start_ms: int
    end_ms: int
    speaker: str
    text: str

    def line(self) -> str:
        return f"[{ts(self.start_ms)}] {self.speaker}: {self.text}"


def build_turns(rec: dict) -> list[Turn]:
    names = rec.get("speakers") or {}
    turns: list[Turn] = []
    for p in rec["phrases"]:
        speaker = names.get(p["speaker"], p["speaker"])
        end = p["t_ms"] + p["dur_ms"]
        last = turns[-1] if turns else None
        if (last and last.speaker == speaker
                and p["t_ms"] - last.end_ms <= TURN_MAX_GAP_MS
                and end - last.start_ms <= TURN_MAX_LEN_MS):
            last.text += " " + p["text"]
            last.end_ms = end
        else:
            turns.append(Turn(p["t_ms"], end, speaker, p["text"]))
    return turns


def chunk_turns(turns: list[Turn], chunk_ms: int = 0, chunk_tokens: int = 0) -> list[list[Turn]]:
    """Split into windows of about chunk_ms of audio or chunk_tokens of
    transcript, on turn boundaries. A short final remainder (under a third of a
    window) is folded into the previous chunk."""
    def size(ts: list[Turn]) -> float:
        if chunk_tokens:
            return sum(ntok(t.line()) for t in ts) / chunk_tokens
        return (ts[-1].end_ms - ts[0].start_ms) / chunk_ms

    chunks: list[list[Turn]] = []
    cur: list[Turn] = []
    cur_tok = 0
    for t in turns:
        full = (cur_tok + ntok(t.line()) > chunk_tokens) if chunk_tokens else \
               (cur and t.start_ms - cur[0].start_ms >= chunk_ms)
        if cur and full:
            chunks.append(cur)
            cur, cur_tok = [], 0
        cur.append(t)
        cur_tok += ntok(t.line()) if chunk_tokens else 0
    if cur:
        if chunks and size(cur) < 1 / 3:
            chunks[-1].extend(cur)
        else:
            chunks.append(cur)
    return chunks


def tail(turns: list[Turn], ms: int) -> list[Turn]:
    if not turns:
        return []
    cutoff = turns[-1].end_ms - ms
    return [t for t in turns if t.end_ms > cutoff]


def load_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text()


def header(rec: dict) -> str:
    speakers = sorted(set((rec.get("speakers") or {}).values())) or ["(unlabelled)"]
    return (f"Title: {rec['title']}\n"
            f"Date: {(rec.get('recorded_at') or '')[:16].replace('T', ' ')}\n"
            f"Duration: {round(rec['duration_seconds'] / 60)} min\n"
            f"Speakers (from voice matching, may be wrong): {', '.join(speakers)}")


class LLM:
    def __init__(self, model: str, effort: str | None):
        self.model = model
        self.effort = effort
        self.client = AsyncAzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version="2025-04-01-preview",
            max_retries=3,
            timeout=600,
        )

    async def __call__(self, system: str, user: str, calls: list[dict], label: str) -> str:
        kwargs = {"reasoning_effort": self.effort} if self.effort else {}
        t0 = time.monotonic()
        for attempt in range(30):
            try:
                r = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    max_completion_tokens=32_000,
                    **kwargs,
                )
                break
            except RateLimitError:
                # The SDK's own retries (max_retries) are short; the per-minute
                # token quota needs a longer wait when several runs share it.
                if attempt == 29:
                    raise
                await asyncio.sleep(min(20 + 10 * attempt, 90))
        u = r.usage
        calls.append({
            "label": label,
            "seconds": round(time.monotonic() - t0, 1),
            "prompt_tokens": u.prompt_tokens,
            "completion_tokens": u.completion_tokens,
            "reasoning_tokens": getattr(u.completion_tokens_details, "reasoning_tokens", 0) or 0,
            "finish_reason": r.choices[0].finish_reason,
        })
        return (r.choices[0].message.content or "").strip()


async def minutes_for(rec: dict, llm: LLM, args) -> dict:
    turns = build_turns(rec)
    chunks = chunk_turns(turns, int(args.chunk_minutes * 60_000), args.chunk_tokens)
    chunk_prompt, coverage_prompt = load_prompt(args.prompt), load_prompt(args.coverage_prompt)
    calls: list[dict] = []
    parts: list[str] = []
    for i, chunk in enumerate(chunks):
        prev = [t for c in chunks[:i] for t in c]
        context = tail(prev, int(args.context_minutes * 60_000))
        new = "\n".join(t.line() for t in chunk)
        user = (
            f"# MEETING\n{header(rec)}\n\n"
            f"# MINUTES SO FAR (read-only)\n{chr(10).join(parts) or '(none: this is the first segment)'}\n\n"
            f"# RECENT CONTEXT (read-only, already covered above)\n"
            f"{chr(10).join(t.line() for t in context) or '(none)'}\n\n"
            f"# NEW SEGMENT {i + 1} of {len(chunks)}: "
            f"[{ts(chunk[0].start_ms)}] to [{ts(chunk[-1].end_ms)}]\n{new}\n"
        )
        if args.target_ratio:
            budget = round(ntok(new) * args.target_ratio / 50) * 50 or 50
            user += (f"\n# LENGTH BUDGET\nThe new segment is about {ntok(new)} tokens. Keep its "
                     f"minutes to about {budget} tokens. Cut wording, not specifics.\n")
        text = await llm(chunk_prompt, user, calls, f"chunk{i + 1}")
        if args.coverage:
            check = (f"# MEETING\n{header(rec)}\n\n# NEW SEGMENT\n{new}\n\n"
                     f"# DRAFT MINUTES\n{text}\n")
            text = await llm(coverage_prompt, check, calls, f"coverage{i + 1}")
        parts.append(text)
        print(f"  {rec['id'][:8]} chunk {i + 1}/{len(chunks)} done", flush=True)

    body = "\n\n".join(parts)
    overview = await llm(load_prompt(args.rollup_prompt),
                         f"# MEETING\n{header(rec)}\n\n# MINUTES\n{body}\n", calls, "rollup")
    speakers = sorted(set((rec.get("speakers") or {}).values()))
    doc = (f"# {rec['title']}\n\n"
           f"**Date:** {(rec.get('recorded_at') or '')[:16].replace('T', ' ')} · "
           f"**Duration:** {round(rec['duration_seconds'] / 60)} min · "
           f"**Speakers:** {', '.join(speakers) or 'unlabelled'}\n\n"
           f"{overview}\n\n## Minutes\n\n{body}\n")
    transcript = "\n".join(t.line() for t in turns)
    return {
        "doc": doc,
        "meta": {
            "id": rec["id"],
            "title": rec["title"],
            "duration_min": round(rec["duration_seconds"] / 60, 1),
            "chunks": len(chunks),
            "transcript_tokens": ntok(transcript),
            "minutes_tokens": ntok(doc),
            "compression": round(ntok(doc) / max(ntok(transcript), 1), 3),
            "prompt_tokens": sum(c["prompt_tokens"] for c in calls),
            "completion_tokens": sum(c["completion_tokens"] for c in calls),
            "reasoning_tokens": sum(c["reasoning_tokens"] for c in calls),
            "seconds": round(sum(c["seconds"] for c in calls), 1),
            "calls": calls,
        },
    }


def settings(args) -> dict:
    prompts = [args.prompt, args.rollup_prompt] + ([args.coverage_prompt] if args.coverage else [])
    digest = hashlib.sha256("".join(load_prompt(p) for p in prompts).encode()).hexdigest()[:12]
    return {
        "model": args.model, "effort": args.effort,
        "chunk_minutes": None if args.chunk_tokens else args.chunk_minutes,
        "chunk_tokens": args.chunk_tokens or None, "target_ratio": args.target_ratio,
        "context_minutes": args.context_minutes, "coverage": args.coverage,
        "prompts": prompts, "prompt_hash": digest,
    }


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--all", action="store_true", help="every recording in cache/recordings")
    ap.add_argument("--model", default="gpt-5.6-luna")
    ap.add_argument("--effort", default="medium", help="reasoning effort; 'none' to omit")
    ap.add_argument("--chunk-minutes", type=float, default=10)
    ap.add_argument("--chunk-tokens", type=int, default=0,
                    help="chunk by transcript tokens instead of minutes")
    ap.add_argument("--target-ratio", type=float, default=0,
                    help="ask for minutes of about this fraction of each segment's tokens")
    ap.add_argument("--context-minutes", type=float, default=2)
    ap.add_argument("--coverage", action="store_true", help="second pass per chunk to fill gaps")
    ap.add_argument("--prompt", default="chunk_v1")
    ap.add_argument("--coverage-prompt", default="coverage_v1")
    ap.add_argument("--rollup-prompt", default="rollup_v1")
    ap.add_argument("--run", help="run name (default: derived from settings)")
    ap.add_argument("--jobs", type=int, default=3, help="recordings processed in parallel")
    ap.add_argument("--force", action="store_true", help="redo recordings already in the run")
    args = ap.parse_args()
    if args.effort == "none":
        args.effort = None

    ids = sorted(p.stem for p in REC_DIR.glob("*.json")) if args.all else args.ids
    if not ids:
        ap.error("give recording ids or --all")
    size = f"t{args.chunk_tokens}" if args.chunk_tokens else f"c{args.chunk_minutes:g}"
    run = args.run or (f"{args.model}-{args.effort or 'noeffort'}-{size}"
                       f"{f'-r{args.target_ratio:g}' if args.target_ratio else ''}"
                       f"{'-cov' if args.coverage else ''}-{args.prompt}")
    out = RUNS / run
    out.mkdir(parents=True, exist_ok=True)
    (out / "settings.json").write_text(json.dumps(settings(args), indent=1))
    llm = LLM(args.model, args.effort)
    sem = asyncio.Semaphore(args.jobs)

    async def one(rec_id: str) -> None:
        if (out / f"{rec_id}.md").exists() and not args.force:
            print(f"skip {rec_id} (exists)")
            return
        rec = json.loads((REC_DIR / f"{rec_id}.json").read_text())
        async with sem:
            print(f"start {rec_id[:8]} {rec['title']} ({rec['duration_seconds'] / 60:.0f} min)", flush=True)
            result = await minutes_for(rec, llm, args)
        (out / f"{rec_id}.md").write_text(result["doc"])
        (out / f"{rec_id}.json").write_text(json.dumps({**settings(args), **result["meta"]}, indent=1))
        m = result["meta"]
        print(f"done  {rec_id[:8]} {m['duration_min']:.0f} min: {m['transcript_tokens']} -> "
              f"{m['minutes_tokens']} tok ({m['compression']:.0%}), {m['seconds']:.0f}s of calls", flush=True)

    results = await asyncio.gather(*(one(i) for i in ids), return_exceptions=True)
    for rec_id, r in zip(ids, results):
        if isinstance(r, Exception):
            print(f"FAILED {rec_id}: {r!r}")
    print(f"\nOutput: {out.relative_to(HERE)}")


if __name__ == "__main__":
    asyncio.run(main())
