# Contributing

Start by running `node examples/first-check.mjs` and `node --test` with Node 24. No dependency installation is needed. The demo deliberately produces integrity ALLOW and exact-text DENY for the same synthetic packet.

Useful first contributions include clearer plain-text explanations, synthetic negative fixtures, packet exporters, readable receipt viewers, and bounded parsing improvements. Keep collectors, account connections, payments and action execution out of this small verifier.

Make one coherent change with a regression test. Security fixes should demonstrate a failing case before the correction. Do not weaken an assertion to get a green run. State the tested runtime and separate PASS, FAIL and NOT_RUN. Test names are not evidence beyond their actual assertions.

Preserve original evidence bytes, deterministic decisions and explicit trust. Never infer PROVED from integrity ALLOW, trust from a signature alone, or authorization from any receipt. A new policy needs a versioned public rule, all decision inputs and explicit missing/conflicting/stale-evidence behavior before it can claim independent reproduction. Do not introduce model-dependent verdicts.

Prefer plain language, meaningful text output and keyboard-friendly tooling. Color must not carry the only meaning. Automated checks are not manual screen-reader validation.

Do not contribute secrets, customer evidence, private service code or internal investigation mechanics. Only contribute code and data you have permission to share. The public project uses Apache-2.0; retain its attribution notices. Open pull requests on the public GitHub repository `zensteagarden/noticer-open`.

## Intention-guided contributions

The Success Contract is a public clarification interface, not an authorization mechanism and not a learning engine. Keep human intention, observable proxy, evidence, verdict and permission distinct. Do not add automatic promotion, hidden scoring, private comparison strategy or model-generated verdicts to this public repository.
