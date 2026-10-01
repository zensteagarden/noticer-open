# Agent guide for Noticer

If you are an AI agent helping somebody use Noticer, begin with their intended outcome, not with an automation recipe.

1. Ask what they are actually trying to make happen.
2. Separate that outcome from the app, API, trigger or workflow they suggested.
3. Reflect the outcome back in plain language.
4. Identify the narrow observable proxy the public verifier can check.
5. State what that proxy does not prove.
6. Ask for confirmation before treating the Success Contract as settled.
7. Treat confirmation as clarification, **not authorization to act**.
8. Keep model reasoning outside the deterministic verdict path.

Communication should be calm, respectful and nonjudgmental. Do not perform intimacy, pressure the user, or use a caring tone as a reason to override their choices.

For the executable helper, run:

```sh
node examples/guided-first-run.mjs
```

For a no-input synthetic demonstration, run:

```sh
node examples/guided-first-run.mjs --demo
```

Read `docs/INTENTION_GUIDE.md`, `docs/SUCCESS_CONTRACT.md`, and `docs/PUBLIC_SCOPE.md` before extending this flow.
