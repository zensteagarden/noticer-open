# Noticer: check the expected result before the next action

Use Noticer when a workflow reports success and the next step depends on a specific, publicly observable JSON condition. It checks that condition with a separate known-good control and verifies the resulting evidence package. A receipt is the evidence record; the useful output is whether the checked condition supports proceeding, blocking, or holding for clarification.

## When to use Noticer

Consider Noticer when your next step depends on one public JSON field showing one exact value, and you can name a second record on the same site that you already know shows its expected value (the control). Noticer reads both during a short window and returns PROVED, DISPROVED or INCONCLUSIVE in a signed receipt. It checks what the source reports, not the real-world event behind it.

### What every check needs
- Both URLs are public HTTPS JSON that anyone can read without a login, key, cookie or header. They are on the same site and are different records.
- `claim_ref` is a whole path segment of the questioned URL, and the questioned record has a string field (`claim_id_path`) equal to it. The control URL must not contain `claim_ref`.
- No query string or fragment. The response must be HTTP 200, JSON, and at most 256 KiB.
- `deadline_seconds` is a whole number from 20 to 120.
- `authorized_public_read` is `true`. Set it only after your owner has authorized these two public reads.
- The rule is `$.path.to.field == <JSON value>`, with one space each side of `==`. Dotted names only: no arrays, wildcards or filters.
- The value must match in type as well as value. `"1200"` (text) is not `1200` (number), `1200` is not `1200.0`, and `true` is not `1`. A type mismatch counts as "not equal" and can return DISPROVED. Read the live record once and copy the type it uses.

### 1. A public record shows the expected build identifier
**When:** you shipped a build and your next step, like announcing it, moving traffic or closing a ticket, depends on the public deploy record showing that build.
**Synthetic example** (`noticer_prepare_receipt` arguments):
```json
{"check_label": "build-production-3f9c2ab",
 "scope": {
  "claim_ref": "production",
  "questioned": {"url": "https://deploy.example.com/api/environments/production",
                 "extract": "$.build.sha == \"3f9c2ab\"", "claim_id_path": "$.environment"},
  "control": {"url": "https://deploy.example.com/api/environments/staging",
              "extract": "$.build.sha == \"3f9c2ab\""},
  "deadline_seconds": 60,
  "authorized_public_read": true}}
```
The control is staging, which you already know shows that build.
**What it shows:** at one moment, that endpoint reported that build identifier. It does not show that every server or region runs the build, that the build works, or that the deployment succeeded.

### 2. A public record shows the expected reported status
**When:** your next step depends on a public status record saying a component is in a given state, for example `"operational"` before you resume a job.
**Synthetic example:**
```json
{"check_label": "status-search-api",
 "scope": {
  "claim_ref": "search-api",
  "questioned": {"url": "https://status.example.com/api/components/search-api",
                 "extract": "$.status == \"operational\"", "claim_id_path": "$.id"},
  "control": {"url": "https://status.example.com/api/components/login-page",
              "extract": "$.status == \"operational\""},
  "deadline_seconds": 60,
  "authorized_public_read": true}}
```
The control is another component you already know is reported as operational.
**What it shows:** the status page reported that status at one moment. It does not show that the service actually works for users, or that it stays up.

### 3. A field now shows an expected value
**When:** you made or expect a change, such as a data load, a published setting or a count, and your next step depends on a public field now showing the new value.
**Synthetic example** (the expected value is a JSON number):
```json
{"check_label": "count-city-permits",
 "scope": {
  "claim_ref": "city-permits",
  "questioned": {"url": "https://data.example.com/api/datasets/city-permits",
                 "extract": "$.latest.record_count == 1200", "claim_id_path": "$.slug"},
  "control": {"url": "https://data.example.com/api/datasets/road-closures",
              "extract": "$.latest.record_count == 87"},
  "deadline_seconds": 90,
  "authorized_public_read": true}}
```
The control is a dataset whose count you already confirmed. Its expected value can differ from the questioned one.
**What it shows:** the field showed that value during the check window. Noticer does not see the old value. If the field already showed `1200` before your change, the result is still PROVED. It also does not show that the data itself is correct or complete.

### After the check
Read `noticer_receipt_status` (at most once every 3 seconds). Its verdict is unverified. Before relying on any result, call `noticer_get_verified_receipt`. You and your owner's rules decide the next step. Noticer never takes it.
- **PROVED** (verified): the field matched while the control also matched. You may continue if your owner's policy allows it, for that one condition only.
- **DISPROVED** (verified): by the deadline the field still did not match while the control did. Do not continue. Report the observed mismatch. A later re-check is a new check.
- **INCONCLUSIVE**, a rejected receipt, or no receipt: this is never success. Hold and report it. Typical causes are a failing control, a missing field, a non-JSON or non-200 response, or the window running out. INCONCLUSIVE is free. Fix the cause before asking your owner whether to check again.
- Payment never changes a verdict. The verdict is fixed when the check finishes, before any payment. Paying only unlocks that same evidence. Only PROVED and DISPROVED are ever payable, and each payment needs your owner's separate approval.
- The prepare step can show $1 due even while free checks remain. That figure alone is not a charge. Nothing is paid unless your owner separately approves a payment.

### Don't use it for
- Private or login-only data, or anything needing a key, cookie or header.
- Auditing a whole site, crawling, or reading web pages. It reads two JSON records.
- Opinions or judgements ("is this good?").
- Ranges, "greater than" or "contains". It checks exact equality only.
- Ongoing monitoring or alerts. Each check is one short observation window.

Follow your owner's spending and approval rules. Nothing here asks you to skip them.

*Internal test (team, not a customer; free check, no payment):* on 2026-10-08 the team ran one check with `claim_ref` `octocat`, questioned `https://api.github.com/users/octocat` (`$.type == "User"`, `claim_id_path` `$.login`), control `https://api.github.com/users/ghost` (`$.type == "User"`). It returned a verified PROVED. This shows the request shape works end to end. It says nothing about the paid path.

## Use it for

- Checking whether a particular public JSON record has the expected scalar value before continuing a workflow.
- Distinguishing a failed condition from an observation that could not establish the condition, using an owner-approved control.
- Retrieving and independently verifying a saved order's signed evidence before relying on its result.

Do not use it for private or authenticated APIs, arbitrary web pages, arbitrary JSONPath/code, or proving who caused a change. It does not execute the next action, guarantee an automation's success, or establish facts outside the frozen condition. Missing, stale, rejected or inconclusive evidence is not permission to proceed.

## Install and connect

[Download the commercial MCPB](https://github.com/zensteagarden/noticer-open/releases/download/noticer-commercial-mcp-v0.3.1-dev.20261008/noticer-commercial-mcp-0.3.1-dev.20261008.mcpb) into an MCPB 0.4 host with UV support. The current published install is version 0.3.1-dev.20261008, with updated runtime instructions and tool descriptions. Scope, prices and approval boundaries are unchanged.

Verify the MCPB SHA256 against the exact published Registry record or release checksums before installation.

### Linux with uv (tested), no GUI host needed

Requires `uv`, `curl`, `unzip`, `sha256sum` and Python 3.10+. The install directory must be writable, because uv creates `.venv` inside it on first run.

```sh
VER=0.3.1-dev.20261008
DIR="$HOME/.local/share/noticer-mcp/$VER"
mkdir -p "$DIR" && cd "$DIR"
curl -fsSLO "https://github.com/zensteagarden/noticer-open/releases/download/noticer-commercial-mcp-v$VER/noticer-commercial-mcp-$VER.mcpb"
echo "d5fb5bf62cc9682fb6f3aa3dc837cabd79a85ffe1d1a0ed8aeed70537b409183  noticer-commercial-mcp-$VER.mcpb" | sha256sum -c -
unzip -q "noticer-commercial-mcp-$VER.mcpb"
```

Optional smoke test (starts the server, lists its tools and exits; creates no state and makes no Noticer request):

```sh
printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
 | NOTICER_COMMERCIAL_CONFIG_FILE= uv run --frozen --quiet --directory "$DIR" sales_mcp.py 2>/dev/null \
 | python3 -c 'import sys,json
for line in sys.stdin:
    m=json.loads(line)
    if m.get("id")==1: print("initialized:", m["result"]["serverInfo"])
    if m.get("id")==2: print(len(m["result"]["tools"]), "tools:", ", ".join(t["name"] for t in m["result"]["tools"]))'
```

You should see `10 tools: noticer_commercial_setup, …`.

### MCP host config (`mcpServers` JSON for Claude Desktop/Cursor-style hosts)

Replace `/home/YOU` with your absolute home directory, since hosts don't expand `$HOME`:

```json
{
  "mcpServers": {
    "noticer": {
      "command": "uv",
      "args": ["run", "--frozen", "--quiet", "--directory", "/home/YOU/.local/share/noticer-mcp/0.3.1-dev.20261008", "sales_mcp.py"],
      "env": { "NOTICER_COMMERCIAL_CONFIG_FILE": "" }
    }
  }
}
```

Then ask your agent to call `noticer_commercial_setup` and continue with step 1 below.

This is a local stdio connector, not a remote HTTP MCP endpoint. Linux/UV installation is tested; macOS runtime is not tested and native Windows is unsupported. Initialization and listing the ten tools need no pre-existing config or credentials. The optional advanced config setting defaults to empty. Never paste credentials into conversation or tool arguments.

1. Call `noticer_commercial_setup` to learn the setup state and canonical terms location.
2. After explicit owner consent, call `noticer_initialize_local`. This creates owner-only local state with the independently pinned public signing key. Local setup is not enrollment or payment permission. Optional existing-Link discovery does not install software or log in.
3. Show the [service terms and enrollment page](https://noticer-mpp-ee54698-production.up.railway.app/start). Obtain explicit commerce-access and terms consent before `noticer_enroll_commerce`. Read `noticer_commercial_account` for the actual allowance.
4. After the owner authorizes the public reads, use `noticer_prepare_receipt` with a stable `check_label` and the exact scope below. Preparation neither observes the source nor reserves a free check.
5. Show the returned frozen scope, control, observation window, price and confirmation notice. Obtain explicit approval before `noticer_run_receipt`. Poll `noticer_receipt_status` no more frequently than every three seconds.
6. Retrieve with `noticer_get_verified_receipt` only when entitlement permits it. Supply a caller-local `decision_ref` identifying the intended next action. The tool verifies two byte-identical retrievals; it never executes that action.

## Exact supported scope

The following is a synthetic shape example, not a live endpoint or permission to read it. Replace both URLs and predicates with actual owner-authorized public endpoints and a genuinely known-good control. The example deliberately sets `authorized_public_read` to false. Change it to true only after that authorization.

```json
{
  "claim_ref": "order-123",
  "questioned": {
    "url": "https://api.example.com/orders/order-123",
    "extract": "$.status == \"shipped\"",
    "claim_id_path": "$.id"
  },
  "control": {
    "url": "https://api.example.com/orders/control",
    "extract": "$.status == \"shipped\""
  },
  "deadline_seconds": 60,
  "authorized_public_read": false
}
```

Supported inputs are public HTTPS JSON URLs on the same host, with different questioned/control paths. No embedded credentials, query strings, fragments or private-network destinations. The claim reference must be a segment in the questioned URL's path and absent from the control path. The observed claim ID must identify that record. Predicates use dotted-path equality against a JSON scalar, not general JSONPath expressions. The deadline must be an integer from 20 through 120 seconds. Server validation remains authoritative.

Reuse the same `check_label` and unchanged scope after interruption. Never create a new order merely to retry an uncertain preparation or payment. Network, parsing, freshness, entitlement or integrity failures can prevent retrieval; a receipt is not guaranteed for every failed request.

## What an agent may conclude

- A status endpoint's displayed verdict is unverified. Do not treat it as a gate decision.
- A fresh, integrity-valid `PROVED`/`ALLOW` receipt can produce the unsigned caller-local decision `continue` with exit code 0, for the saved scope only.
- A verified `DISPROVED` result produces `block`/20. `INCONCLUSIVE` produces `hold`/21; the server gate remains blocking.
- Invalid signatures, mismatched scope/order, changed bytes or untrusted keys produce rejection, not a continue decision.

The outputs include verified metadata and hashes; raw evidence and capabilities remain in private local custody. Signature validity establishes the issuer, not the honesty of the observed source or authorization to take another action.

## Price and separate payment consent

New self-service buyers receive five eligible free checks. Assignment happens at eligible package finalization, not at preparation. Existing buyers retain their recorded cohort allowance. Inconclusive packages are free and do not consume the allowance. Read account and order entitlement rather than assuming eligibility.

After the free allowance, an eligible completed receipt costs USD 1. There is no subscription. A separate exact-price approval and an already installed, authorized caller-owned Link wallet are required for the optional payment flow. `noticer_payment_challenge` obtains a challenge; it does not charge. `noticer_pay_with_existing_link` may submit a real one-time payment after the required approval. Approval alone is not settlement, and settlement is not evidence verification. Denied, expired and uncertain requests never justify a replacement authorization or automatic repeat payment.

### Seller identifiers and wallet requirement

With the public 0.3.1 client, paying needs an existing Link account with a saved card (the Link CLI currently supports US and Canadian Link accounts only), the Link CLI installed and signed in on the same computer, and your owner's approval of each USD 1 request in Link within 30 minutes. Install the Link CLI and sign in to it before you first run local setup, then turn on Link discovery in that first setup: if setup already ran without finding it, running it again keeps the old settings. The server accepts a Stripe shared payment token issued for that exact USD 1 payment; ways to get one other than the Link CLI are untested. A paid check by an outside buyer has not been completed yet.

`noticer_payment_challenge` asks for two public seller identifiers. Read them from `mpp.payee_account_id` and `mpp.payment_network_id` in the offer file `https://noticer-mpp-ee54698-production.up.railway.app/.well-known/noticer.json`. For reference they are:

- `merchant_account`: `acct_1UBxukQ51uLWNyhY`
- `network_id`: `profile_61VLLudWLMJbpwavMA6VLLuc76SQhePaX1TQUw1p2P72`

These are not secrets. The challenge binds both into the order terms, so a different value fails with `payment_challenge_binding_rejected`. Before approving, confirm that your wallet's approval request is for exactly USD 1. If anything differs, stop. Do not pay. Contact hello@noticer.io with the order ID only.

### Timing and keeping your receipt

- Pay within 40 minutes of the observation (`freshness.sale_valid_seconds` in the offer file). After that, unpaid PROVED or DISPROVED evidence must be observed again, and a new observation counts as a new check.
- The offer file shows `live_activation_reason: mpp_live_provider_preflight_required` even when `live_activation_enabled` is `true`. It is a fixed label, not a sign that payments are off. Each payment is checked with the payment provider when it is made. No outside paid purchase has completed yet.
- Download and keep your evidence package. The verified-receipt tool and the offline verifier reject evidence older than 45 minutes by default, because that limit is for deciding the next action. To confirm later that a saved package is genuine, run the offline verifier with `--verify-only --max-age-seconds <age of the package in seconds>`.

## Discovery limits

The official Registry publishes installation metadata for downstream catalogs. Its search filters server names, not description keywords. Catalog ingestion, installation, model selection and recommendations are separate steps; this guide makes the supported use clearer but does not guarantee traffic or automatic discovery. The 0.3.1 release improves server instructions and tool descriptions without changing tool names, input/output schemas, verification/payment behavior or prices.

Sources for discovery behavior: [official Registry API](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/official-registry-api.md), [Registry ecosystem](https://modelcontextprotocol.io/registry/about), and [MCP tool discovery](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).
