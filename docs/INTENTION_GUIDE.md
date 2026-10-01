# Intention before automation

Noticer should help a person state what they actually want to become true before a workflow is treated as a design problem.

The human owns the intention. An agent may clarify, decompose and propose, but it must not silently replace, broaden or invent the user's definition of success.

The public starter uses a small **Success Contract** to keep four things separate:

1. the human intention;
2. the required outcome the person would recognize as success;
3. the observable proxy this public verifier can actually check;
4. what that proxy does **not** establish.

A Success Contract is not an authorization token. Understanding what somebody wants does not grant permission to open accounts, read private systems, mutate data, spend money or take any external action.

After the person confirms the contract, a workflow may attempt the outcome under separately granted authority. Verification remains independent. The actor that attempted the work does not get to convert its own success message into a Noticer verdict.

The public verifier is deliberately narrower than the philosophy. Today it can reproduce disclosed packet integrity and exact-text checks. It does not observe live destinations and it does not prove subjective human outcomes. The gap must stay visible.

## Guidance for an AI agent

If an AI agent is helping a user, it should behave like a careful guide rather than a workflow vending machine.

- Ask what the person is trying to have happen in the world, not only which app or trigger they want.
- Separate the desired outcome from the mechanism proposed to achieve it.
- Ask the fewest questions needed to remove a consequential ambiguity.
- Reflect the understood intention back in plain language before proposing automation.
- Name the observable proxy and explicitly state what it cannot prove.
- Keep authorization separate from understanding.
- Prefer reversible technical choices when the user has not expressed a consequential preference.
- Never put a model on the deterministic verdict path.
- Never treat warmth, empathy or confidence as authority to decide for the user.

A useful short form is:

> Understand before acting. Observe before believing.
>
> The user defines success. Automation attempts it. Noticer reports what the evidence can establish.

## Public/private boundary

This public guide does not contain Noticer's private candidate selection, comparison, scoring, challenge-generation, learning or promotion mechanics. It defines only the public handoff from clarified human intent to a disclosed check.
