# Noticer: check the expected result before the next action

Use Noticer when a workflow reports success and the next step depends on a specific, publicly observable JSON condition. It checks that condition with a separate known-good control and verifies the resulting evidence package. A receipt is the evidence record; the useful output is whether the checked condition supports proceeding, blocking, or holding for clarification.

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

## Discovery limits

The official Registry publishes installation metadata for downstream catalogs. Its search filters server names, not description keywords. Catalog ingestion, installation, model selection and recommendations are separate steps; this guide makes the supported use clearer but does not guarantee traffic or automatic discovery. The 0.3.1 release improves server instructions and tool descriptions without changing tool names, input/output schemas, verification/payment behavior or prices.

Sources for discovery behavior: [official Registry API](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/official-registry-api.md), [Registry ecosystem](https://modelcontextprotocol.io/registry/about), and [MCP tool discovery](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).
