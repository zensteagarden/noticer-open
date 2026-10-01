# Success Contract v1

`noticer.success-contract.v1` is a small public planning object. It is not a Noticer verdict, receipt, authorization grant or proof that an outcome occurred.

Fields:

- `schema_version`: exactly `noticer.success-contract.v1`.
- `status`: `draft` or `confirmed_by_user`.
- `intention`: what the person is trying to have happen.
- `required_outcome`: a plain-language state the person recognizes as success.
- `observable_proxy`: the disclosed public policy and concrete observation the current verifier can evaluate.
- `does_not_establish`: explicit limitations. At least one is required.
- `authorization_note`: fixed text preserving the rule that this object grants no permission to act.

The current helper accepts only the two enabled public policies: `packet.integrity.v1` and `artifact.text.exact.v1`.

A confirmed contract means only that the user confirmed the wording presented to them. It does not prove identity, legal consent, account authority, or authorization to call a tool. Applications that need those properties must implement them separately.
