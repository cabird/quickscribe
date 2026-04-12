# Creating Reliable LLM Evaluation Rubrics for Wikis
- **Duration:** 11m
- **Attendees:** Speaker 1
- **Purpose:** Describe a data-driven rubric-building approach that makes LLM evaluations of wikis reliable, repeatable, and prescriptive.

## Executive Summary
Speaker 1 described a practical method used at GitHub to convert unreliable, free-form LLM ratings into a valid, repeatable rubric for evaluating wikis. The team used models to discover evaluation dimensions across several hundred wikis, ranked small sets of examples per dimension to produce total orders, and constructed five-point score definitions with exemplars and counter-examples. The resulting system produces stable scores (by running multiple exemplars and runs), explains why a wiki received a score, and gives specific, actionable recommendations to improve each dimension; cost and scaling remain operational concerns.

### Discussion Threads

#### 1) The "strawberry" failure mode and user responsibility
Context: Speaker 1 framed a common LLM failure (simple character counting) as a symptom of misusing models without invoking tools.
- Speaker 1 noted that models often fail trivial character-level tasks (the "strawberry" example) because tokenization hides character granularity.
- He argued that the core issue is user judgment: knowing when to ask the model to use tools (e.g., write code) to perform deterministic tasks.
- He emphasized that even weak models can produce correct results if asked to use an appropriate tool or program the solution.
Outcome: **Resolved** — The team accepts that evaluation procedures must encode when to rely on raw LLM output versus tooling or programmatic checks; rubric design should incorporate guidance on using tools where appropriate.

#### 2) Models are unreliable at raw numeric ratings; need for structured rubrics
Context: Speaker 1 explained why direct 1–5 ratings from LLMs are meaningless without a benchmark or measuring stick.
- Speaker 1 observed that free-form numeric ratings are inconsistent (models avoid extremes and fabricate confidence).
- He recommended narrowing the task (specific dimension), providing explicit criteria, and giving exemplars to improve reliability.
Outcome: **Resolved** — Use dimension-specific rubrics plus exemplars rather than direct unconstrained numeric ratings to obtain meaningful scores.

#### 3) Data-driven discovery of evaluation dimensions using models
Context: Speaker 1 described the process of using LLMs to surface the relevant evaluation axes across hundreds of wikis.
- Speaker 1 said the team collected ~300–500 wikis and asked models to list categories/themes across batches, then consolidated overlapping outputs (MapReduce style).
- They arrived at ~16 meaningful dimensions (e.g., discoverability, API coverage, usage coverage).
Outcome: **Resolved** — Use LLM-assisted clustering/aggregation to identify evaluation dimensions from a broad dataset.

#### 4) Ranking small sets and producing total orders to create score exemplars
Context: Speaker 1 explained how to turn relative rankings into absolute rubric levels.
- He described repeatedly asking a model to rank 4–5 wikis on a single dimension, using those rankings to build a total order for ~500 wikis per dimension.
- The ordered list was then split into quintiles to define 1–5 scores; for each score the team generated "what it is," "what it is not," and example pages.
- He noted that pairwise or small-set comparisons (2–4 items) produce better discrimination than single-item scoring.
Outcome: **Resolved** — Build rubrics by ranking small sets, deriving total orders, and mapping ordered populations to score buckets with exemplars.

#### 5) Increasing validity and replicability with exemplars and multiple passes
Context: Speaker 1 covered methods to stabilize scoring and produce actionable feedback.
- Speaker 1 indicated that they ran each dimension scoring three times with different exemplars (and sometimes different models) to reduce variance; this increased token cost (≈$5 per wiki) but improved consistency.
- The rubric entries include prescriptive suggestions (e.g., add descriptive links to move from 3→4) so ratings are also actionable.
Outcome: **Open** — The approach is validated qualitatively and found valuable by GitHub, but optimization for cost and scalable automation remains unresolved.

## Key Quotes
- Speaker 1, on model failures and responsibility: "If you ask a model how many Rs are in 'strawberry' and it doesn't know, the problem is you, not the model — you don't know where the model is strong and where it is weak."
- Speaker 1, on direct ratings: "If you give it a scale of one to five, it will never give you a 1 and it will never give you a 5."
- Speaker 1, on building dimensions: "We asked a model to give us categories for batches of wikis, then did a MapReduce to see what came up — we settled on something like 16 different categories."
- Speaker 1, on exemplars and prescriptive feedback: "We split the ordered list into five populations, then had the model describe what a 1 is, what a 1 is not, and give an example; that made the rubric specific and actionable."
- Speaker 1, on cost vs value: "Scoring a wiki was not cheap — it cost like $5 of tokens — but it actually had value: it told you why and how to improve."

## Open Questions
- How can the multiple-run, exemplar-based scoring workflow be optimized to reduce token cost while preserving reliability? (Speaker 1)
- Which concrete tooling or programmatic checks should be paired with rubric items to handle deterministic checks (e.g., character counts)? (Speaker 1)
- How well does this rubric-building method generalize to other content types beyond wikis (docs, tutorials, API references)? (Speaker 1)

## Next Steps
- Implement the rubric workflow for new wiki evaluations: use model-assisted dimension discovery, small-set ranking to build total orders, split into quintiles, and generate exemplar-based score descriptions.
- Run multiple exemplar-based scoring passes for a pilot subset to measure variance and token cost; instrument outputs for prescriptive suggestions and compare perceived value.
- Schedule a follow-up discussion focused on cost-optimization, model selection, and automation of deterministic checks (no date specified).

## Parking Lot
- Cost and scalability optimization for multi-run scoring pipeline (deferred by Speaker 1).
- Formal selection criteria for which models to use for ranking vs explanation vs tooling invocation (deferred by Speaker 1).

## Topic Tags
LLM evaluation, rubrics, wikis, exemplars, model reliability, evaluation dimensions, cost optimization