# Recognition pilot results

**Status: BLOCKED / NOT_RUN**
**Date:** 2026-10-17 (UTC)

## Execution feasibility

- **Host:** GitHub Copilot Coding Agent sandbox (`runnervm8k3b6`).
- **Model/version:** Not exposed by this runtime.
- **OS:** Linux x86_64, kernel `6.17.0-1022-azure`.
- **Fresh isolated sessions:** Not available through an authorized capability exposed here. This environment provides no supported way to launch sessions guaranteed not to inherit this issue/repository context, the answer key, or earlier responses, while recording independent session provenance. No nested agents were launched.

## Outcome and evidence

The first blocker occurred before trial 1: no qualifying isolated-session runner was available. **0 of 48 planned trials were started.** No trial prompts were sent, responses or session IDs were generated, and no results were scored. Per-trial tool availability and timing are not applicable. Counts and outcome denominators are therefore not applicable; this is not a zero-success result.

The prepared kit was inspected at pinned commit [`e9cf4e4`](https://github.com/zensteagarden/noticer-open/tree/e9cf4e4f96c7683ca2e0e3881423bbff23232f34/experiments/agent-recognition-v1): [protocol](https://github.com/zensteagarden/noticer-open/blob/e9cf4e4f96c7683ca2e0e3881423bbff23232f34/experiments/agent-recognition-v1/PROTOCOL.md), [manifest](https://github.com/zensteagarden/noticer-open/blob/e9cf4e4f96c7683ca2e0e3881423bbff23232f34/experiments/agent-recognition-v1/study-manifest.json), [trial order](https://github.com/zensteagarden/noticer-open/blob/e9cf4e4f96c7683ca2e0e3881423bbff23232f34/experiments/agent-recognition-v1/trial-order.csv), [scorecard](https://github.com/zensteagarden/noticer-open/blob/e9cf4e4f96c7683ca2e0e3881423bbff23232f34/experiments/agent-recognition-v1/scorecard.csv), and [scorer](https://github.com/zensteagarden/noticer-open/blob/e9cf4e4f96c7683ca2e0e3881423bbff23232f34/experiments/agent-recognition-v1/score.py). The scorecard remains unreviewed and `NOT_RUN`. There are no raw transcripts or session-provenance records. Independent review is `NOT_RUN`.

Phase 0 discovery was not attempted. Phases 2 and 3 were not run. No connector, real account, public read, receipt, enrollment, or payment activity occurred. This provides no evidence about model recognition, catalog discovery, MCP execution, or customer outcomes.

## Next action

Connect an authorized, auditable fresh-session runner that guarantees per-trial context isolation and captures model/version and session provenance; only then run this fixed pilot.
