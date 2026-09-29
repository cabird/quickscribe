You are given the detailed minutes of a recorded conversation, written
segment by segment with [mm:ss] timestamps. Write the overview that goes at the
top of the document. Use only the minutes; add nothing that is not in them.

Output markdown in exactly this shape, omitting a section only if it would be
empty:

**Gist:** 2-4 sentences on what the conversation was for, what was worked
through, and where it ended up.

**Topics:** the topic headings in order, each as "[mm:ss] Topic", separated
by " · ".

## Decisions
- [mm:ss] What was decided, and by whom.

## Action items
- [mm:ss] **Name** — what they committed to (by when, if stated).

## Open questions
- [mm:ss] What was raised and left unresolved.

Keep the speakers' hedging. Use the timestamp of the point in the minutes
where each item appears. No preamble, no code fences.
