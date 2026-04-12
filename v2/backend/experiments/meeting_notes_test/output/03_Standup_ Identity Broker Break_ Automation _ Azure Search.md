# Standup: Identity Broker Break, Automation & Azure Search
- **Duration:** 48m
- **Attendees:** Speaker 1, Speaker 2, Speaker 3, Speaker 4, Speaker 5
- **Purpose:** Weekly standup to surface blockers, coordinate Azure Search experiments, discuss repo hosting and automation for reproducible workstation setup

## Executive Summary
Team members reported progress and blockers across three main areas: a local identity-broker update that bricked a developer machine and prompted investment in reproducible setup automation; ongoing Azure Search experiments focused on using GOC to re-rank the top ~200 search results; and repo/hosting decisions (MSR Central vs ADO/personal git) for internal projects. Q4 budget approvals were announced and a Veritrail/Word conversation is scheduled for the week. Several technical follow-ups remain open (publishing automation scripts, continued Azure Search experiments, repo migration and MSR Central usability issues).

### Discussion Threads

#### Identity broker update, recovery and reproducible automation
Context: A pushed fix for the identity broker seriously disrupted Speaker 1's development machine and drove work to automate system reprovisioning.
- Speaker 1 described an identity-broker update that "hard bricked" their Ubuntu machine, forcing a reinstall and prompting them to create scripts and declarative recipes for quick reprovisioning.
- Speaker 1 will publish the automation (Kumtaya/Nix-flake style recipes) to their sandbox repo so the process can be reused and imported into a team-managed place later.
- Speaker 1 and others exchanged notes about YubiKey/smart-card manager issues on Windows and Linux; Speaker 1 verified they are now unblocked once VPN and agency access are restored.
Outcome: **Open** — Speaker 1 is unblocked for immediate work but will publish automation to prevent recurrence; publishing action remains.

#### Azure Search experiments and GOC re-ranking
Context: Ongoing experiments aim to apply GOC within a constrained re-ranking of top search results rather than indexing all documents.
- Speaker 5 reported mixed but promising results after Thursday's meeting; the team better understands how to run experiments in the partner ML environment and iterated on GOC settings.
- The current approach: build a temporary "index" over the top ~200 search results and test whether GOC can re-rank more effectively than existing re-ranking.
- Speaker 5 will continue iterations this week to try to obtain measurable lift under the constraint.
Outcome: **Open** — experiments continue; iterative runs planned to validate whether GOC gives lift in the constrained re-ranking scenario.

#### MSR Central vs ADO/personal git for repos and workflow migration
Context: Team discussed where to host repos intended for consumption by other teams and private experimentation.
- Speaker 1 recommended putting Graphic Gen. 4 on MSR Central for consumption by other teams; lazy graph/legacy repos can remain on ADO as archival.
- Speaker 3 noted MSR Central can host private repos (internal vs private) and flagged some UX issues when importing from ADO.
- Team consensus: prefer MSR Central for shared/internal consumption; use ADO or personal git for private experiments and archival where appropriate.
Outcome: **Resolved** — Use MSR Central for shared/internal repos (Speaker 1 confirmed). Use ADO/personal git for private/archival repos. Migration/import details remain to be executed.

#### Data focus: finance and healthcare datasets
Context: Dasha (Speaker 4) and others discussed prioritizing finance data (and healthcare secondarily) for upcoming work.
- Speaker 4 noted Jonathan and Igor favor a finance framing and that there is considerable finance data available beyond the hackathons; Jonathan will re-engage this week.
- Speaker 4 is exploring finance-focused ideas and continuing to learn SOMA; healthcare was noted as lower priority due to less urgency.
Outcome: **Open** — Team to prioritize finance use cases and discuss specifics with Jonathan this week.

#### MSR Central usability and workflow automation (collective signal)
Context: Speaker 3 is moving a guinea pig project to MSR Central and experimenting with automated workflows to address PR volume and contributor friction.
- Speaker 3 migrated Collective Signal to MSR Central and will use it to prototype genetic workflows to reduce PR friction and align reviewer processes.
- Speaker 3 reported MSR Central's UI can be confusing (spinner issues) but will proceed with experiments there.
Outcome: **Open** — Workflow experiments on MSR Central are underway; success criteria are to reduce PR friction.

#### Admin: Q4 budget and Veritrail discussion
Context: Admin updates and upcoming meetings.
- Speaker 4 announced Q4 budget approvals, including additional funds for Uncharted and some honoraria; Speaker 4 will handle the budget follow-ups.
- Speaker 4 reminded the group of an upcoming meeting this week about Veritrail potentially being used by Word folks.
Outcome: **Resolved** (budget approval) and **Open** (Veritrail discussion scheduled for this week).

#### Terminal/model UX (tab completion, prompt sync)
Context: Speaker 2 raised UX concerns about model-backed terminal behavior and possible tab-completion features.
- Speaker 2 asked whether tab completion on filenames is feasible and noted inconsistencies where the terminal prompt and filesystem outputs appear temporarily out of sync.
- The team did not resolve technical paths but acknowledged the need to intercept tab and manage prompt sync for speed.
Outcome: **Open** — UX/implementation questions remain; technical follow-up required.

## Decisions
1. Put Graphic Gen. 4 repository on MSR Central for consumption by other teams (Speaker 1).
2. Use MSR Central for most shared/internal repositories; use ADO or personal git for private experiments and archival legacy repos (Speaker 1).
3. Q4 budget approved with additional funds allocated to Uncharted and some honoraria (Speaker 4).

## Action Items
| Action | Owner | Deadline | Notes |
|---|---:|---:|---|
| Publish workstation reprovisioning automation (Kumtaya/Nix-style recipes) to sandbox repo | Speaker 1 |  | Speaker 1 committed to sharing scripts; no hard deadline stated |
| Move Graphic Gen. 4 repo to MSR Central and verify import | Speaker 1 |  | Confirm private vs internal visibility as needed |
| Continue Azure Search / GOC experiments to attempt re-ranking lift on top 200 results | Speaker 5 |  | Iterative experiments in partner ML environment; no deadline stated |
| Prototype genetic workflows on MSR Central using Collective Signal repo to reduce PR friction | Speaker 3 |  | Use Collective Signal as guinea pig; monitor PR/merge metrics |
| Handle Q4 budget follow-ups and honorarium distributions | Speaker 4 |  | Speaker 4 to coordinate budget admin work |
| Attend Veritrail → Word discussion and report outcomes | Speaker 4 | This week | Meeting scheduled within the next few days per Speaker 4 |

## Key Quotes
- Speaker 1, on the identity-broker update and recovery: "They bricked my machine... I'm writing code to make sure I never have to do this again."
- Speaker 1, on reprovisioning goals: "I'm going to be back up and running like 10 minutes."
- Speaker 5, on Azure Search experiments: "We're able to work within their test ML environment a lot better to create experiments and iterate... building an index on the fly over the top 200 search results to see if it can re-rank them better."
- Speaker 3, on MSR Central UX: "The spinner is a lie."
- Speaker 4, on budget: "All of our budget stuff got approved for Q4."

## Open Questions
- Speaker 1 / Team: When exactly will the reprovisioning scripts be published and where should they be imported for team use? (Speaker 1 raised)
- Speaker 5: Can GOC produce measurable lift in the constrained re-ranking scenario, and what metrics define success? (Speaker 5 raised)
- Speaker 3 / Team: What is the recommended workflow for importing repos from ADO into MSR Central to avoid UX/import issues? (Speaker 3 raised)
- Speaker 2: Is intercepting the tab key and prompt-sync feasible for the model-backed terminal to allow fast, local tab completion? (Speaker 2 raised)
- Speaker 4: What are the concrete next steps and success criteria from the Veritrail → Word meeting? (Speaker 4 raised)

## Next Steps
- Speaker 1 to publish automation scripts to the sandbox repo as soon as possible.
- Speaker 5 to continue GOC/Azure Search experiment iterations and report results in follow-up meetings.
- Speaker 3 to run workflow experiments on MSR Central with Collective Signal and report outcomes.
- Speaker 4 to follow up on Q4 budget tasks and attend the Veritrail discussion this week.
- Team to migrate Graphic Gen. 4 to MSR Central and confirm visibility and import behavior.
- No specific next meeting time was scheduled; next regular standup remains the cadence for updates.

## Parking Lot
- Implement tab-completion and synchronous prompt behavior for the model-backed terminal (Speaker 2).
- Iterate on how to automatically import large numbers of repos from ADO into MSR Central without UI friction (Speaker 3).
- Make the to-do.txt content generation less prescriptive and more varied (Speaker 2 suggested; deferred for later UX improvements).

## Topic Tags
Azure Search, identity broker, automation, MSR Central, repo migration, budget, YubiKey