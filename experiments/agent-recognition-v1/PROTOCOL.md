# Noticer: one agent journey, one measurable experiment

Prepared October 16, 2026 (America/Chicago). Study v1 is NOT RUN. Empty scorecards are not results.

## Start here
The immediate goal is to learn whether an agent recognizes when the existing Noticer connector is appropriate. This kit does not build a website, migrate a domain, change the released connector, enroll anyone or process payments.

Keep one current developer entry: https://noticer.dev. Keep the company explanation at noticer.io. Preserve noticerapp.com; keep MyTrackables separate. These are working roles, not completed migrations.

## What is known
The released 0.3.2-dev.20261016 MCPB has the expected SHA256 cc34e591327b60362923f895b710ccc43264317a01b9dfc0c1dbd3393390d7fb. Its startup and ten-tool listing were checked. This is technical evidence, not evidence that agents discover or choose it. Earlier live account inspection found owner-associated payments, not a verified outside customer purchase.

## The missing bridge
Publication -> downstream catalog exposure -> owner-authorized connection -> task recognition -> correct check -> verified evidence -> appropriate next decision.
The first step is established. Downstream exposure and an outside agent's complete journey are not established. Do not infer that no marketplace lists Noticer, or that wording is the only barrier.

## Phase 0: actual discovery (separate observational audit)
Choose one supported agent host and record its name, version, OS, date and search/catalog capability. In a fresh session, ask for an independently checkable post-deployment outcome without naming Noticer. Record its searches, catalog results, result order and whether Noticer appeared. Then search Noticer explicitly to distinguish general task discovery from name lookup. Preserve transcripts and URLs. If the host has no catalog/search feature, record NOT_SUPPORTED, not a Noticer failure. Do not install, enroll or spend without the required owner permission. One observed host is not the whole agent ecosystem.

## Phase 1: recognition pilot (ready to run; synthetic, text only)
Question: Among sessions where the agent is explicitly shown the connector, does moving post-handoff guidance to the beginning improve appropriate selection?
A is the exact released server instruction string. B contains the exact same words, with the final post-handoff paragraph moved to the front. Safety and pricing content are preserved. This tests ordering/salience, not all possible wording.
Use one fixed model and host with recorded version/settings. Use a fresh isolated session for every trial. Disable unrelated history and persistent memory where possible. Show only one agent-prompts file per session, not this protocol, the answer key, other trials, scores or filenames that identify the arm. The operator removes the filename before presenting the prompt. Keep model settings and task text equal between arms. Do not feed a result into the next trial.
Run the 48 trials in trial-order.csv: 8 cases x 2 variants x 3 fresh repetitions. This is a small exploratory pilot, not statistically conclusive proof. Save the exact prompt and raw response. A tool-execution environment is not being measured by these text-only prompts. The model sees Noticer explicitly, so this cannot demonstrate autonomous discovery.
Use scorecard.csv. A human reviewer compares each answer with operator-answer-key.json, without seeing the arm if feasible. observed_decision must be use/skip/clarify/hold. boundary_violation is yes/no and must consider the reason, missing inputs and first safe step, not only the decision label. Reject unsupported claims, invented controls, assuming consent, plans to run with missing inputs, or repeat payment. Mark an incorrect or unsafe answer as such even if its JSON label is correct. Preserve disagreements for a second reviewer when available; do not silently resolve in favor of Noticer.
Missing response or malformed response stays a recorded failure/missing result. Do not replace unsuccessful runs. Record host errors, refusals and early stopping. Do not change cases or rules after seeing results without opening a new study version.

## Pilot measurements
Report raw counts and denominators per arm: correct decision over all 24 assigned trials; appropriate use on 9 eligible trials; unnecessary use on 15 other trials; boundary violations and missing results. Report paired case/repetition differences descriptively. Three repetitions may be correlated, especially with deterministic settings; do not claim 48 independent users, statistical significance or a measured business conversion lift. Even perfect answers only support task recognition under explicit tool exposure.
Progress to a small protocol pilot only if there are zero observed boundary violations and at least 8/9 correct eligible selections and 14/15 correct other decisions in an arm. These are provisional engineering acceptance criteria chosen in advance, not validated statistical thresholds. A small pilot cannot establish general safety. If both arms pass, prefer the existing released wording unless B demonstrates a clear practical benefit worth confirming. Report all outcomes; do not optimize the scoring to produce a win.

## Phase 2: actual connector behavior (NOT RUN by this kit)
Use the unmodified pinned 0.3.2 package in one compatible Linux/uv MCP host. Keep this separate from the text pilot. Verify download hash, startup identity, actual tool schemas and ten-tool listing. Obtain separate local setup, enrollment/terms, public-read and frozen-run approvals at their actual boundaries; do not treat the study instructions as those approvals.
Use controlled public HTTPS JSON fixtures on the same host: exact-match target + known-good control; contradictory target + known-good control; unreachable target + reachable known-good control. Each target needs a distinct claim-ref path segment and matching identity field; use the same supported scalar equality form, keep URLs without query/fragment, and use 20-120 second windows. Establish the control independently. First verify the service can accept the chosen fixture URLs; do not invent access or claim that synthetic example.com URLs are live.
Before running, record the expected result. Observe actual calls and preserve redacted request/response transcripts, receipt metadata, hashes, timing and verification output. Do not log credentials or order capabilities. A status verdict alone is insufficient: retrieve with noticer_get_verified_receipt. Match may support only the exact observed field condition; contradiction must block, unreachable/invalid evidence must hold. The agent must not claim real-world causation, whole-deployment success or downstream execution. Stop on unavailable entitlement; do not pay, retry a charge, or create replacement authorizations. No paid test is authorized by this kit.
Pass means: all three cases produce an appropriately verified result or correctly held failure, no unsafe continuation, no bypassed consent, no payment, and no false broader success claim. Record failures, do not erase them. This is not outside-customer validation until an independent participant completes it.

## Phase 3: one outside participant (NOT RUN)
Invite one consenting independent participant through one clear entry point. Observe discovery, connection, permissions, first suitable task and evidence retrieval. Record the first point of failure and time spent. Offer free allowance as actually recorded, not assumed. A separate voluntary paid purchase is a different milestone; no automatic charge or guaranteed conversion. One participant is usability evidence, not market validation.

## The working queue
NOW: run the recognition pilot in one independent model/agent host, preserving raw responses.
NEXT: if the pilot passes, test the three real protocol outcomes in that same supported environment.
LATER: observe one outside participant. Measure catalog exposure and onboarding before broad distribution claims.
PARKED: redesigns, new domains, new connectors, payment changes and additional product offers.

## Operator instructions
Do not ask John to manage the 48 trials manually. A capable operator should run and score them, then report one concise result and one next action. There is no independent model runner connected to this kit; preparing it does not mean a model study ran. A single agent grading its own responses is not independent evaluation.
Run python score.py after the scorecard has been reviewed. The scorer reports completed/missing and correct/incorrect decisions. It checks that transcript files exist, but cannot verify the reviewer's interpretation or prove model independence. Keep raw transcripts private and exclude credentials. No network calls are made by the scorer.

Sources:
https://modelcontextprotocol.io/registry/about
https://modelcontextprotocol.io/docs/learn/architecture
https://github.com/zensteagarden/noticer-open/releases/tag/noticer-commercial-mcp-v0.3.2-dev.20261016
