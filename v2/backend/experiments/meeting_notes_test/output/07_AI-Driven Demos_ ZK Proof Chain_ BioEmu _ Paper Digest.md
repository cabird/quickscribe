# AI-Driven Demos: ZK Proof Chain, BioEmu & Paper Digest
- **Duration:** 18m
- **Attendees:** Speaker 1, Speaker 2, Speaker 3, Speaker 4, Speaker 5
- **Purpose:** Share short demos and experiences building AI-enabled tools and solicit follow-ups and collaboration.

## Executive Summary
Three short demos showcased AI-enabled workflows and tools: Speaker 1 demonstrated a distributed "proof chain" ZK proof pipeline built rapidly using coding agents; Speaker 3 (Jacob) demoed a BioEmu-based protein ensemble viewer and analysis app built with AI assistance and Azure scaling in mind; Speaker 4 (Akshay) presented a Paper Digest copilot skill that ingests a personal paper corpus to produce actionable experimental guidance. Attendees agreed to share artifacts and follow up offline for deeper technical dives; no formal decisions were recorded, but multiple owners volunteered to share demos and coordinate next-session signups. Open items include deeper technical reviews, production scaling details for BioEmu, and broader access to the Paper Digest skill.

### Discussion Threads

#### Proof Chain: distributed ZK pipeline and coding-agent accelerated development
Context: Speaker 1 described building a distributed pipeline to produce and verify zero-knowledge proofs across chains, emphasizing use of coding agents and human expert collaboration.
- Speaker 1 explained the goal: generate a zero-knowledge proof from a source chain using an existing Nova ZK prover, generalize it, send it to a target chain, verify, and finish the transaction flow.
- Speaker 1 described the workflow used: initial design via conversational ChatGPT (GBT-52) to produce a markdown design file, follow-up development using GitHub Copilot CLI, cloud code, and iterative agent reviews producing multiple markdown reviews that were aggregated to prioritize fixes.
- Speaker 1 noted that a human expert (Srinasatis) provided crucial domain knowledge; agent reviews surfaced ~20 top issues that were missed in the author's manual review, improving code quality.
- Speaker 1 reported a functioning distributed system ready for pull request after roughly seven partial days of work, estimating a 4x–8x speedup versus prior non-agent workflows.
Outcome: **Resolved** — Speaker 1 reached a pull-request-ready state for the proof chain; follow-up technical questions to be handled offline with Speaker 1.

#### BioEmu demo: protein ensemble visualization and analysis
Context: Speaker 3 (Jacob) demonstrated an application built largely with AI that uses Microsoft Research's BioEmu model to generate protein ensembles and provide exploratory analytics.
- Speaker 3 described BioEmu as a protein ensemble generator that models protein motion and produces multiple conformations beyond a single static prediction.
- The app includes a Mol* viewer showing animated ensembles, statistics (radius of gyration, contact maps, flexibility profiles, secondary structure charts), and a comparison view versus AlphaFold static predictions.
- Speaker 3 highlighted a context-aware copilot on the app that adapts to user expertise level and helps explain views; backend scaling plans use Azure ML and Foundry endpoints for batch/parallel processing for larger workloads.
- Speaker 3 credited fast iteration with the AI-for-Science team collaboration (Frank No) and noted the app was built with earlier codec versions (Sonics) as a proof of concept before upgrading to newer codecs.
Outcome: **Open** — Demo succeeded as a prototype; production scaling, integration details, and customer/partner rollout remain open and require follow-up on Azure ML configuration and batch workflows.

#### Paper Digest: personalized RAG copilot for ML paper insights
Context: Speaker 4 (Akshay) presented "Paper Digest," a copilot skill that ingests a personal corpus of ML papers and produces concise experimental guidance and hyperparameter suggestions.
- Speaker 4 described the problem: remembering experimental details across many papers; the skill indexes papers, performs RAG over the personal corpus, and returns distilled recommendations (datasets, learning rates, model sizes validated in papers).
- Speaker 4 emphasized that generic copilot/GPT without the personalized RAG context gave poor results, while the curated corpus produced actionable guidance that improved their experimental workflow.
- Speaker 4 offered to share the skill with others.
Outcome: **Open** — The skill works for the present indexed corpus; sharing and broader testing with more papers and users is pending (Speaker 4 to distribute the skill).

#### Logistics, sharing, and future demos
Context: Brief closing items about sharing artifacts, help with setup, and scheduling future demos.
- Speaker 5 invited people to reach out for help setting things up and offered coordination for future demo slots.
- Multiple presenters encouraged offline follow-ups for technical questions and artifact sharing.
Outcome: **Deferred** — Scheduling the next demo roster and deeper technical workshops was deferred for future coordination (no date set).

## Action Items
| Action | Owner | Deadline | Notes |
|---|---:|---:|---|
| Share Paper Digest copilot skill and access details with interested attendees | Speaker 4 |  | Speaker 4 volunteered to share; no deadline specified. |
| Provide demo artifacts, code links, or a short walkthrough for the BioEmu app (including Azure ML scaling notes) | Speaker 3 |  | Jacob offered follow-up; no deadline specified. |
| Be available for follow-up technical questions about the ZK proof chain and provide design/code pointers | Speaker 1 |  | Speaker 1 invited people to find them after the session. |
| Coordinate future demo slots and assist attendees with getting setups running | Speaker 5 |  | Speaker 5 offered lightweight help and next-session coordination. |

## Key Quotes
- Speaker 1, on agent-augmented development: "After seven days I got a fully working distributed system that's ready for pull request... this represents like a 4 to 8x boost." (about coding agents + human expert workflow)
- Speaker 1, on collaboration: "Combining agents with human experts is super important — in this case I picked the Srinasatis brain, he's a distributed-systems expert."
- Speaker 3 (Jacob), on BioEmu value: "Proteins aren't static — BioEmu helps predict how those proteins will move, so you can view an ensemble rather than just a static structure."
- Speaker 4 (Akshay), on personalized RAG: "I tried asking GPT or Copilot without the RAG context and it provided no useful information at all. Ingesting curated papers helps a lot."

## Open Questions
- How will the proof chain handle cross-chain failure modes and verification latency in production? (asked by Speaker 1; requires technical follow-up)
- What Azure ML configuration, resource types, and batch-parallel strategies will BioEmu require at production scale? (raised by Speaker 3; needs detailed design)
- How robust is Paper Digest's extraction across diverse paper formats and larger corpora, and what validation exists for extracted hyperparameters? (raised by Speaker 4)
- Can the context-aware copilot in the BioEmu app be generalized to other scientific visualization apps, and what are the privacy/access implications for shared model endpoints? (raised by attendees during Q&A)

## Next Steps
- Attendees will contact presenters for offline technical follow-ups and artifact sharing (Paper Digest, BioEmu demo materials, proof chain code/design).
- Speaker 4 to share the Paper Digest skill; Speaker 3 to provide BioEmu demo artifacts and Azure scaling notes; Speaker 1 to accept follow-up questions about the proof chain.
- Speaker 5 will help coordinate signups for the next demo session and offer assistance to anyone needing setup help.
- No next meeting date was set; follow-ups will be scheduled individually or via the coordinator (Speaker 5).

## Parking Lot
- Deeper technical workshop on coding-agent review process and how to aggregate multi-agent findings (raised by Speaker 1).
- Formal production hardening plan for the ZK proof chain (raised by attendees).
- Larger-scale user testing and performance benchmarking for Paper Digest across bigger corpora (raised by Speaker 4).
- Scheduling and curation of demos for the next session (raised by Speaker 5).

## Topic Tags
Zero-knowledge proofs, BioEmu, protein modeling, Paper Digest, RAG, coding agents, Azure ML