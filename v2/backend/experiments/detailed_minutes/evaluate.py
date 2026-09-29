# /// script
# requires-python = ">=3.11"
# dependencies = ["openai", "python-dotenv", "tiktoken"]
# ///
"""Score a minutes run by question answering, plus a grounding spot-check.

For each recording in the run:
1. Questions. A separate model reads the transcript and writes specific factual
   questions with reference answers. Cached per recording in cache/questions/
   so every run is scored on the same questions.
2. Answers. The answer model answers every question from each source on its own:
   the transcript (ceiling), QuickScribe's search_summary and meeting_notes
   (the existing baselines), and the run's minutes.
3. Judging. The judge model grades each answer against the reference:
   correct 1, partial 0.5, missing 0, wrong 0 (tracked separately).
4. Grounding. The judge checks a sample of minutes bullets against the
   transcript: supported, unsupported, or misattributed.

Usage:
    uv run evaluate.py runs/<run>            # evaluate every recording in the run
    uv run evaluate.py runs/<run> --ids <id> # just some

Writes runs/<run>/eval/<id>.json and runs/<run>/eval/report.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
from pathlib import Path

from minutes import HERE, LLM, REC_DIR, build_turns, header, ntok

QDIR = HERE / "cache" / "questions"

QUESTION_PROMPT = """You write an exam that tests whether a set of notes captured
everything important in a recorded conversation. Read the transcript and write
{n} questions whose answers are specific and checkable from the transcript.

Spread them across the whole conversation (beginning, middle, end) and across
these kinds:
- specific facts: numbers, dates, amounts, names, products, places
- attribution: who said, proposed, or objected to something
- decisions and commitments: who will do what, by when
- reasons: why someone holds a view or why something was decided
- nuance: hedged or tentative statements, disagreements, changes of mind
- loose ends: questions raised or issues left unresolved
- details mentioned in passing that someone might later need

Avoid questions answerable from the title alone, and avoid trivia about
audio problems or greetings. Each answer should be one or two sentences.

Return JSON: {{"questions": [{{"q": "...", "answer": "...", "timestamp": "mm:ss",
"kind": "fact|attribution|decision|reason|nuance|loose_end|detail"}}]}}"""

ANSWER_PROMPT = """Answer each question using ONLY the source document below.
If the source does not contain the answer, reply exactly "NOT IN SOURCE".
Do not guess or use outside knowledge. Be brief and specific.

Return JSON: {"answers": [{"i": <question number>, "answer": "..."}]}"""

JUDGE_PROMPT = """Grade each candidate answer against the reference answer.
- "correct": matches the reference in substance (wording may differ).
- "partial": gets part of it, or is vaguer than the reference in a way that
  loses a specific (a name, number, date, or qualifier).
- "missing": says NOT IN SOURCE or does not answer.
- "wrong": states something that contradicts the reference.

Return JSON: {"grades": [{"i": <question number>, "grade": "correct|partial|missing|wrong"}]}"""

GROUNDING_PROMPT = """Check each numbered statement from a set of meeting minutes
against the transcript.
- "supported": the transcript says this (paraphrase is fine).
- "misattributed": the content is in the transcript but said by someone else.
- "overstated": the transcript supports a weaker or more hedged version.
- "unsupported": the transcript does not say this.

Return JSON: {"checks": [{"i": <statement number>, "verdict": "supported|misattributed|overstated|unsupported", "note": "short reason if not supported"}]}"""

SCORE = {"correct": 1.0, "partial": 0.5, "missing": 0.0, "wrong": 0.0}


async def ask_json(llm: LLM, system: str, user: str, calls: list, label: str) -> dict:
    text = await llm(system, user, calls, label)
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(text)


def transcript_text(rec: dict) -> str:
    return "\n".join(t.line() for t in build_turns(rec))


async def questions_for(rec: dict, llm: LLM, calls: list) -> list[dict]:
    QDIR.mkdir(parents=True, exist_ok=True)
    path = QDIR / f"{rec['id']}.json"
    if path.exists():
        return json.loads(path.read_text())["questions"]
    n = max(8, min(40, round(rec["duration_seconds"] / 60 / 3)))
    data = await ask_json(llm, QUESTION_PROMPT.format(n=n),
                          f"# MEETING\n{header(rec)}\n\n# TRANSCRIPT\n{transcript_text(rec)}",
                          calls, "questions")
    path.write_text(json.dumps({"model": llm.model, **data}, indent=1))
    return data["questions"]


def numbered(questions: list[dict], key: str = "q") -> str:
    return "\n".join(f"{i + 1}. {q[key]}" for i, q in enumerate(questions))


async def score_source(name: str, source: str | None, questions: list[dict],
                       answerer: LLM, judge: LLM, calls: list) -> dict:
    if not source:
        return {"source": name, "tokens": 0, "score": None, "grades": {}}
    ans = await ask_json(answerer, ANSWER_PROMPT,
                         f"# SOURCE\n{source}\n\n# QUESTIONS\n{numbered(questions)}",
                         calls, f"answer:{name}")
    by_i = {a["i"]: a["answer"] for a in ans["answers"]}
    pairs = "\n\n".join(
        f"{i + 1}. Q: {q['q']}\n   Reference: {q['answer']}\n   Candidate: {by_i.get(i + 1, 'NOT IN SOURCE')}"
        for i, q in enumerate(questions))
    graded = await ask_json(judge, JUDGE_PROMPT, pairs, calls, f"judge:{name}")
    grades = {g["i"]: g["grade"] for g in graded["grades"]}
    counts = {k: sum(1 for g in grades.values() if g == k) for k in SCORE}
    return {
        "source": name,
        "tokens": ntok(source),
        "score": round(sum(SCORE.get(g, 0) for g in grades.values()) / len(questions), 3),
        "counts": counts,
        "per_question": [{"q": q["q"], "kind": q.get("kind"), "reference": q["answer"],
                          "answer": by_i.get(i + 1), "grade": grades.get(i + 1)}
                         for i, q in enumerate(questions)],
    }


def minutes_bullets(doc: str) -> list[str]:
    body = doc.split("## Minutes", 1)[-1]
    return [ln.strip()[2:] for ln in body.splitlines()
            if ln.strip().startswith("- ") and len(ln.strip()) > 30]


async def grounding(rec: dict, doc: str, judge: LLM, calls: list, k: int) -> dict:
    bullets = minutes_bullets(doc)
    sample = random.Random(rec["id"]).sample(bullets, min(k, len(bullets)))
    data = await ask_json(judge, GROUNDING_PROMPT,
                          f"# TRANSCRIPT\n{transcript_text(rec)}\n\n# STATEMENTS\n"
                          + "\n".join(f"{i + 1}. {b}" for i, b in enumerate(sample)),
                          calls, "grounding")
    checks = [{"statement": sample[c["i"] - 1], **c} for c in data["checks"] if 0 < c["i"] <= len(sample)]
    verdicts = [c["verdict"] for c in checks]
    return {
        "sampled": len(sample),
        "supported_rate": round(verdicts.count("supported") / max(len(verdicts), 1), 3),
        "counts": {v: verdicts.count(v) for v in ("supported", "misattributed", "overstated", "unsupported")},
        "problems": [c for c in checks if c["verdict"] != "supported"],
    }


async def evaluate(rec_id: str, run: Path, qgen: LLM, answerer: LLM, judge: LLM, args) -> dict:
    rec = json.loads((REC_DIR / f"{rec_id}.json").read_text())
    doc = (run / f"{rec_id}.md").read_text()
    calls: list = []
    questions = await questions_for(rec, qgen, calls)
    sources = {
        "transcript": transcript_text(rec),
        "search_summary": rec["baselines"].get("search_summary"),
        "meeting_notes": rec["baselines"].get("meeting_notes"),
        "minutes": doc,
    }
    scored, ground = await asyncio.gather(
        asyncio.gather(*(score_source(n, s, questions, answerer, judge, calls) for n, s in sources.items())),
        grounding(rec, doc, judge, calls, args.grounding_sample),
    )
    result = {"id": rec_id, "title": rec["title"], "duration_min": round(rec["duration_seconds"] / 60),
              "questions": len(questions), "sources": {s["source"]: s for s in scored},
              "grounding": ground, "calls": calls}
    (run / "eval").mkdir(exist_ok=True)
    (run / "eval" / f"{rec_id}.json").write_text(json.dumps(result, indent=1))
    print(f"evaluated {rec_id[:8]} {rec['title'][:50]}", flush=True)
    return result


def pct(x) -> str:
    return "—" if x is None else f"{x:.0%}"


def report(results: list[dict], run: Path) -> str:
    names = ["transcript", "search_summary", "meeting_notes", "minutes"]
    lines = [f"# Evaluation: {run.name}", "",
             "QA score = share of questions answered correctly (partial = half). "
             "Tokens = size of the source the answerer read.", "",
             "| Recording | Min | Qs | " + " | ".join(f"{n} score / tok" for n in names) + " | Grounded |",
             "|---|---|---|" + "---|" * len(names) + "---|"]
    for r in sorted(results, key=lambda r: -r["duration_min"]):
        cells = [f"{pct(r['sources'][n]['score'])} / {r['sources'][n]['tokens']:,}" for n in names]
        lines.append(f"| {r['title'][:40]} | {r['duration_min']} | {r['questions']} | "
                     + " | ".join(cells) + f" | {pct(r['grounding']['supported_rate'])} |")
    tot_q = sum(r["questions"] for r in results)
    avg = []
    for n in names:
        rs = [r for r in results if r["sources"][n]["score"] is not None]
        q = sum(r["questions"] for r in rs)
        avg.append(f"{pct(sum(r['sources'][n]['score'] * r['questions'] for r in rs) / q if q else None)}"
                   f" / {sum(r['sources'][n]['tokens'] for r in rs):,}")
    g_n = sum(r["grounding"]["sampled"] for r in results)
    g_ok = sum(r["grounding"]["counts"]["supported"] for r in results)
    lines.append(f"| **All ({len(results)})** | | {tot_q} | " + " | ".join(avg) + f" | {pct(g_ok / g_n if g_n else None)} |")
    wrong = {n: sum(r["sources"][n].get("counts", {}).get("wrong", 0) for r in results) for n in names}
    lines += ["", "Wrong (contradicting) answers: " + ", ".join(f"{n} {c}" for n, c in wrong.items()), ""]
    kinds: dict[str, list[float]] = {}
    for r in results:
        for pq in r["sources"]["minutes"].get("per_question", []):
            kinds.setdefault(pq["kind"] or "?", []).append(SCORE.get(pq["grade"], 0))
    lines += ["## Minutes score by question kind", ""] + [
        f"- {k}: {pct(sum(v) / len(v))} of {len(v)}" for k, v in sorted(kinds.items())]
    lines += ["", "## Minutes misses (graded missing or wrong)", ""]
    for r in results:
        for pq in r["sources"]["minutes"].get("per_question", []):
            if pq["grade"] in ("missing", "wrong"):
                lines.append(f"- **{r['title'][:40]}** [{pq['grade']}] {pq['q']} — ref: {pq['reference']}"
                             + (f" — got: {pq['answer']}" if pq["grade"] == "wrong" else ""))
    lines += ["", "## Grounding problems", ""]
    for r in results:
        for p in r["grounding"]["problems"]:
            lines.append(f"- **{r['title'][:40]}** [{p['verdict']}] {p['statement']} — {p.get('note', '')}")
    return "\n".join(lines) + "\n"


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", type=Path)
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--question-model", default="gpt-5.6-terra")
    ap.add_argument("--answer-model", default="gpt-5.6-luna")
    ap.add_argument("--judge-model", default="gpt-5.6-terra")
    ap.add_argument("--grounding-sample", type=int, default=15)
    ap.add_argument("--jobs", type=int, default=3)
    args = ap.parse_args()
    run = args.run if args.run.is_absolute() else (Path.cwd() / args.run)
    ids = args.ids or sorted(p.stem for p in run.glob("*.md"))
    qgen, judge = LLM(args.question_model, "medium"), LLM(args.judge_model, "low")
    answerer = LLM(args.answer_model, "low")
    sem = asyncio.Semaphore(args.jobs)

    async def one(rec_id: str):
        async with sem:
            return await evaluate(rec_id, run, qgen, answerer, judge, args)

    results = await asyncio.gather(*(one(i) for i in ids), return_exceptions=True)
    ok = []
    for rec_id, r in zip(ids, results):
        if isinstance(r, Exception):
            print(f"FAILED {rec_id}: {r!r}")
        else:
            ok.append(r)
    if ok:
        text = report(ok, run)
        (run / "eval" / "report.md").write_text(text)
        print("\n" + text)


if __name__ == "__main__":
    asyncio.run(main())
