# Research lab meeting: leadership shift and agent AI demos
- **Duration:** 115m
- **Attendees:** Chris W., Darren, Speaker 3
- **Purpose:** Lab town-hall to discuss MSR leadership changes, confirm near-term communication/cadence, and share agent-AI demos and project updates.

## Executive Summary
Leadership at MSR has changed (new research stewardship under Igor and Michael); the lab reviewed implications, committed to increasing internal communication, and planned a short information-collection period to surface facts before further interpretation. The bulk of the meeting was demos: Darren (agentic reasoning and memory primitives), Nathan (Project Invincible — an agent dashboard), Christian (session-transcript-as-memory indexing), Spencer (agent swarm pipelines), and Andrea (Grid FM topology + OPF pipeline). Outcomes: immediate increases in team cadence and a Project Green learning week were endorsed; technical threads (verification, security, productionization of agent workflows) remain open for follow-up.

### Discussion Threads

#### 1) Leadership change at MSR and immediate lab posture
Context: Chris opened by addressing the recent reorg (Peter/Kevin stepping back; Igor and Michael in new roles) and the team's need to sense-make without rumor.
- Chris W. framed the change as strategic and new, not clearly good or bad yet; he urged waiting, listening, and preparing clear, consistent messaging. He described meetings with Igor and Michael and asked leads to align communications.
- Darren echoed the need for purposeful interpretation and proposed an information‑sharing plan (Project Green week).
- Speaker 3 emphasized treating the move as intentional and not speculating about personal motives.
Outcome: **Open** — short-term actions agreed (see Next Steps) to gather facts and increase communication; longer-term impacts and priorities under Igor/Michael remain unknown.

#### 2) Communication cadence and information sharing
Context: the team wants to avoid rumor and ensure consistent two-way communications while leadership settles in.
- Chris W. asked leads to be attentive to consistent communications and proposed increasing meeting cadence (lead series and demo hour) and calling a follow-up meeting in two weeks.
- Speaker 3 proposed a week of focused learning for CAD Lab (Project Green) to surface shared facts and align understanding.
- Chris agreed to up cadence (demo hour adjustments and more frequent short meetings) and take the lead on collating learnings from his incoming meetings with Igor and Michael.
Outcome: **Resolved** — Chris W. will increase meeting cadence and call a follow-up meeting; CAD Lab will do a Project Green learning week (coordination tasks assigned in Action Items).

#### 3) Agentic AI research & demos (general)
Context: multiple demos showed practices and prototypes for agentic workflows, memory, and tooling.
- Darren presented "Almada" agentic reasoning + memory primitives, entity‑centric memory (entity cards), subtext memory (reasoning over unknowns), Schemify (web entity extraction and schema discovery), model-free concept mapping, and a "clarity grammar" / memory spec for running and comparing RAG variants. He reported strong early results and a reference-0 paper (aka.ms/grz).
- Nathan showed Project Invincible, a centralized dashboard for managing many agents (registrations, queued questions, asynchronous interactions) to reduce context switching; it uses a protocol for agents to register projects, queue questions, and poll status.
- Christian presented a session-transcript-as-memory system: ingesting recorded agent sessions (VS Code, Copilot, CLI, Cloud Code), producing summaries, context snapshots, and full transcripts; search tools (keyword-first, transcript fallback, LLM fallback) were tuned iteratively and used to rehydrate context and automate repetitive tasks.
- Spencer described an "Agent Swarm" architecture with multiple specialized agents (deep researcher, idea generator, critic, IP agent, TPM/tester, HR evaluator), file-based handoffs and GitHub Actions workflows that spawn agent containers and file pull requests for work products.
Outcome: **Open** — prototypes demonstrated utility and complementary strengths; next steps are to share artifacts, standardize a few tool primitives (session-indexing, MCProtocol endpoints, knowledge graph access), and scope verification and security work. Technical productionization decisions deferred.

#### 4) Grid FM (topology + OPF pipeline)
Context: Andrea presented the Grid FM pipeline to produce realistic synthetic power-grid topologies from public data for foundational-model training and simulation.
- Speaker 3 (Andrea) explained the data sources (OpenStreetMap for topology, EIA for hourly demand and generator inventories), topology extraction and cleaning steps, parameter estimation (resistances, thermal limits), demand allocation, and iterative OPF solving (DC/AC) with solver relaxations where necessary.
- Results: pipeline solved DC and AC OPF across the continental US for sample peak/off-peak hours for most states, with economic realism (states with renewables show lower computed costs). The pipeline produces connected bus-branch models that are solver-verifiable.
Outcome: **Open** — technical prototype validated state-level runs; next steps include expanding to interconnections, improving parameter estimation, and integrating ML-model workflows. Further work will address fidelity, scaling, and ML training datasets.

#### 5) Admin / onboarding / aliases
Context: small but immediate admin fixes needed for aliases and onboarding new lab members.
- Chris W. noted missing aliases (Disa, Chen Chen, Erin) and announced Way (Wayway) as new PM/co-lead.
- Speaker 3 confirmed fixing missed aliases and committed to updating group aliases.
Outcome: **Resolved** — Speaker 3 will update aliases and Way is confirmed as PM / co-lead (see Decisions & Action Items).

### Decisions
1. Chris W. will increase internal meeting cadence and schedule a follow-up lab meeting in approximately two weeks to share learnings after Project Green and his meetings with new leadership (confirmed by Chris W.).
2. The lab will run a focused Project Green learning week for CAD Lab to surface information about the reorg and tooling (endorsed by Chris W.).
3. Way (Wayway) will be onboarded as PM and co-lead for the lab and will assist coordination and ramp activities (confirmed by Chris W.).
4. All presenters were asked to upload their slides and artifacts to the lab SharePoint for dissemination (requested and confirmed by Chris W.).

### Action Items
| Action | Owner | Deadline | Notes |
|---|---:|---:|---|
| Prepare and share a refined lab 2‑pager + white paper about the lab portfolio and messages for leadership conversations | Chris W. |  | Chris referenced ongoing refinements and meetings with Igor and Michael. |
| Host/coordinate a Project Green learning week for CAD Lab and collect learnings | Chris W. |  | Chris requested CAD Lab take a focused week to learn Project Green; coordination and scope to be defined. |
| Fix and update group aliases (add Disa, Chen Chen, Erin, Way; remove obsolete entries) | Speaker 3 |  | Speaker 3 acknowledged missed aliases and will update lists. |
| Upload presentation slides and demo artifacts to SharePoint: Darren, Nathan, Christian, Spencer, Andrea | Darren; Nathan; Christian; Spencer; Andrea |  | Chris requested all presenters place slides in SharePoint for broader team access. |
| Share Darren’s reference-0 paper link and supporting artifacts in SharePoint | Darren |  | Darren already noted aka.ms/grz; asked to post supporting materials. |
| Share Christian’s session-memory deck and tooling notes to SharePoint | Christian |  | Christian said he would drop his deck in chat; requested to publish. |
| Continue Grid FM expansions (interconnection-level runs, ML integration) and post status | Andrea |  | Andrea to run larger-area experiments and document results for lab review. |

### Key Quotes
- Chris W., on visibility and presence: "I encourage all of you to turn your cameras on so that you can participate as full human beings in these kinds of meetings."
- Chris W., on the reorg posture: "It's not about whether it's good or bad, it's about what we do."
- Chris W., on lab opportunity: "We are in a real moment where we get to test agency and will and priorities and values."
- Darren, describing agentic memory approach: "Transform complex problems into verified composable solutions through task decomposition and self‑validating code generation."
- Nathan, on worker experience with many agents: "Consolidate situational alignments to reduce that context switching."
- Christian, on agent-session memory: "Session transcripts are already recorded — use those transcripts as memory and make them searchable."
- Speaker 3 (Andrea), on data constraints for power-grid work: "Real grid data is protected, not available, and public grids are fully synthetic."

### Open Questions
- Chris W. / group: What specific priorities will Igor and Michael set for MSR in the coming months? (asked by Chris W.; awaiting input from Igor/Michael)
- John McClane / group: What remains of TNR (Peter/Kevin responsibilities) after the reorg? (asked by John in the meeting; unresolved)
- Team: What verification and automated testing primitives are required to make agentic code outcomes production-safe? (raised during demos; who owns verification not yet assigned)
- Speaker 3: How will SISO's "head of research" hat translate into resourcing, evaluation, and central coordination of MSR research? (asked by Chris W./Speaker 3; unclear)
- Speaker 3: What governance, security, and compliance guardrails must we set for agentic workflows before broader production use? (raised by Speaker 3 near meeting close)

### Next Steps
- Chris W. will consolidate learnings from his one‑on‑ones with Igor and Michael and report back at the two‑week follow-up meeting.
- CAD Lab will perform a Project Green focused learning week; outcomes will be shared in the follow-up meeting.
- The demo series cadence will increase (demo hour frequency to be adjusted; Chris to confirm exact schedule) and a follow-up lab meeting will be scheduled in ~2 weeks.
- Presenters will upload slides and artifacts to SharePoint for broader team review prior to the next meeting.

### Parking Lot
- Security/compliance framework for agentic systems (Speaker 3 raised; deferred for focused follow-up).
- Formal standardization of agent tooling primitives (session-index API, MCP endpoints, common knowledge-graph interfaces) — deferred to technical working group.
- Deep productionization decisions for multi-agent pipelines (scaling, orchestration, persistent agent instances, billing/cost models) — deferred for deliberate design review.
- TNR ownership and residual responsibilities after reorg (raised by John McClane) — deferred pending leadership clarification.

## Topic Tags
leadership change, agent AI, session memory, multi-agent workflows, Grid FM, Project Green, meeting cadence