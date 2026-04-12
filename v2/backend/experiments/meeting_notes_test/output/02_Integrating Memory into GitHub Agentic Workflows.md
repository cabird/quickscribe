# Integrating Memory into GitHub Agentic Workflows
- **Duration:** 16m
- **Attendees:** Jonathan, Chris
- **Purpose:** Discuss integrating persistent memory into GitHub agentic workflows, share experimental results, and agree next steps for collaboration and dissemination.

## Executive Summary
Jonathan demoed and explained GitHub Agentic Workflows and how memory could be injected to improve agent behavior and efficiency. He reported experiments that extract the embedding-graph/community-detection portion of GraphRAG0 to merge session memories and diaries, yielding a measured 5–10% performance lift; he plans to run nightly aggregation of recent sessions and evaluate utility. Chris and Jonathan agreed to publish the presentation on MSR Central, to produce a short write-up of recent interviews with the GraphRAG team (with Carmen), and to coordinate cross-team work with Darren and Alejandro; several integration and scheduling details remain open and will be resolved via follow-ups.

### Discussion Threads

#### Publishing presentation and repo location
Framing: Jonathan asked where to publish the latest "presentation maker" artifact.
- Jonathan asked whether to put the work in a public git repo or on MSR Central.
- Chris expressed preference that "the powers that be would prefer on MSR Central."
- Outcome: Jonathan confirmed he will put the presentation on MSR Central and keep the latest version available there.
- Outcome label: Resolved (Jonathan to publish on MSR Central).

#### Overview and opportunity of GitHub Agentic Workflows
Framing: Jonathan provided a primer on what Agentic Workflows are and why they matter.
- Jonathan explained agentic workflows as higher-level, agent-based automations (not just deterministic bash scripts) that can interact with PRs, commits, issues, and external tools via Copilot CLI-like interfaces.
- He gave examples: nightly wiki updates, automated daily reports as issues, automated refactor PRs, chained agent reviewers, and a potential marketplace for workflows.
- He emphasized security constraints the GitHub team is focusing on (agents should not get unrestricted access to secrets) and the monetization model (charging for CPU/minutes).
- Chris noted this is a strong developer-productivity opportunity that maps to the team’s work and asked Jonathan to be an advocate with GitHub.
- Outcome label: Open (Opportunity validated; further technical integration and specific memory placement remain to be designed).

#### Memory integration experiments (session memories + diaries)
Framing: Jonathan summarized experiments to merge session memories and diaries and the design choices taken.
- Jonathan ran experiments comparing verbatim session-history GraphRAG0 to a redesigned pipeline that extracts the embedding-graph + community detection + diversity sampling portion of GraphRAG0.
- Jonathan reported the embedding graph + community-detection approach gives a 5–10% lift in performance metrics and is now pulled out and ready to run.
- He described the proposed runtime: scheduled aggregation (hourly/nightly) that extracts useful bits from recent sessions into long-term memories; evaluation will be retrospective by checking if stored memories would have avoided later false starts.
- Chris encouraged trying Darren’s embedding/memory tooling; Jonathan said he will try Darren’s tool on session histories.
- Outcome label: Resolved (approach chosen — embedding graph/community detection from GraphRAG0 will be used in the session memory pipeline); Implementation/testing in progress.

#### Interviews with the GraphRAG team and write-up
Framing: Jonathan and Carmen interviewed seven people on the GraphRAG team to surface practices, issues, and opportunities.
- Jonathan summarized that they have initial findings, an internal HTML exploration, themes extracted, and plan to produce a short doc/deck (and possibly an A1 pager) to share with leadership and partners.
- Chris asked for a concise deliverable to share broadly; Jonathan expects to have a write-up by early next week (possibly sooner).
- Jonathan also requested that Carmen’s contributions be recognized appropriately because some work sits outside conventional SDE metrics.
- Outcome label: Open (write-up in progress; target delivery early next week).

#### Coordination with Alejandro and forming a small research team
Framing: Jonathan asked about collaboration status with Alejandro and potential team resources.
- Jonathan reported Alejandro had fires and tentative delays; Chris said Alejandro mentioned he is getting a small dedicated research team to work on related work and suggested re-engaging him.
- Chris committed to reach out to Alejandro and recommended scheduling an initial one-off meeting with Alejandro, Jonathan, and Darren to align.
- Jonathan proposed a lightweight, recurring sync (start slow cadence then increase), noting short ad-hoc meetings with Darren are high value.
- Outcome label: Open (Chris to contact Alejandro and schedule an initial meeting; ongoing coordination to be set).

## Decisions
1. Jonathan will publish the presentation and keep the latest version on MSR Central. (Confirmed by Jonathan)
2. The session-memory merge will use the embedding-graph + community-detection portion extracted from GraphRAG0 (the redesign Jonathan validated with experiments). (Confirmed by Jonathan)
3. Jonathan will run Darren’s embedding/session-history tooling on session histories to evaluate integration. (Jonathan)
4. Jonathan and Carmen will produce a short write-up (doc/deck/A1 pager) of the GraphRAG-team interviews to share with leadership and partners. (Jonathan, Carmen)
5. Chris will reach out to Alejandro to reconnect, arrange a one-off meeting with Alejandro, Jonathan, and Darren, and then establish an appropriate cadence. (Chris)

## Action Items

| Action | Owner | Deadline | Notes |
|---|---:|---:|---|
| Publish the presentation on MSR Central and maintain latest copy there | Jonathan |  | Jonathan confirmed he will do this |
| Incorporate embedding-graph/community-detection portion of GraphRAG0 into the session-memory pipeline and run scheduled aggregation (hourly/nightly) | Jonathan | end of week | Jonathan reported pipeline nearly ready; evaluation method defined (retrospective utility checks) |
| Try Darren’s memory/embedding tool on session histories and report results | Jonathan | end of week | Jonathan to coordinate with Darren during their weekly chat |
| Produce short write-up (doc/deck/A1 pager) summarizing seven interviews and recommendations | Jonathan & Carmen | early next week | Deliverable intended for Chris and leadership review |
| Reach out to Alejandro and schedule one-off meeting with Alejandro, Darren, Jonathan | Chris |  | Chris to reconnect and initiate meeting scheduling |
| Consider setting recurring sync (Jonathan, Darren, Alejandro) after initial meeting | Chris |  | Start with one-off, then adjust cadence as needed |

## Key Quotes
- Jonathan, asking about hosting: "Is this something I can just put on a public git repo? It's not part of my work, but it's tangential. Would I get in trouble putting this on a public repo or should I go through MSR Central?"
- Chris, on hosting preference: "I think the powers that be would prefer on MSR Central probably."
- Jonathan, on agentic workflows: "What if instead of a bash script I actually have a markdown file that describes a workflow and we give that to Copilot CLI or cloud code and we give it the tools to interact with PRs and commits and let it do the thing."
- Jonathan, on security: "The agent should never have access to secrets, for instance, because you don't know what they're going to do."
- Jonathan, on experimental result: "If we replace... and pull out that portion of GraphRAG0 we get like a 5 to 10% lift in terms of performance."
- Chris, on opportunity: "This sounds like a great thing for us investing because it's right near sweet spot area developer productivity stuff."

## Open Questions
- How exactly will memories be surfaced to agents inside a running workflow (API, sidecar, retrieval pattern)? (Raised by Jonathan)
- What are the precise security/access controls for memories in agent runs (beyond "no access to secrets")? (Raised by Jonathan)
- What are the detailed acceptance criteria and evaluation thresholds for the memory utility metric (how large a utility improvement is actionable)? (Raised by Jonathan)
- When exactly will Alejandro’s new small research team be operational and how much capacity will they have to collaborate? (Raised by Jonathan / to be answered by Alejandro/Chris)
- What packaging/format will be used for a possible marketplace listing for memory-aware workflows (if pursued)? (Raised by Chris/Jonathan)

## Next Steps
- Jonathan will publish the presentation on MSR Central and keep it updated.
- Jonathan will finalize and run the session-memory pipeline using the extracted embedding-graph/community-detection approach; testing and evaluation to proceed (target: end of week).
- Jonathan will try Darren’s memory tooling on session histories and report back.
- Jonathan and Carmen will complete the interview write-up and share with Chris and leadership (target: early next week).
- Chris will contact Alejandro to reconnect and schedule an initial meeting with Alejandro, Jonathan, and Darren; subsequent recurring cadence to be determined after that meeting.

## Parking Lot
- Broader, more systematic interviews across the larger lab to generalize findings beyond the GraphRAG team (deferred for now; raised by Jonathan).
- Detailed marketplace/monetization strategy for agentic workflows and packaged workflows (deferred to future discussion; raised by Jonathan/Chris).

## Topic Tags
GitHub Agentic Workflows, memory, GraphRAG, session memories, MSR Central, interviews, collaboration