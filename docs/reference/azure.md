# Azure reference (non-Fabric)

Local cheat-sheet. Source: Microsoft Learn (via MCP). Covers subscription-level Azure: cost budgets, Bicep/ARM deployment, CLI auth.

---

## Cost budgets (`Microsoft.Consumption/budgets`)

- ARM resource, usually at **subscription scope**. **Alert-only** — never blocks or stops spend; actual cost control is the capacity pause bracket (project doc §5).
- **Ours (live):** `gutenberg-fingerprint-monthly` — $50/mo, alerts at 50%/90% actual + 100% forecasted → sam.vanwilligen@gmail.com. Declared in `infra/budget.bicep`.
- Schema essentials (API `2023-11-01`):
  - `category`: `Cost` (dollars) or `Usage`
  - `amount` + `timeGrain`: `Monthly` | `Quarterly` | `Annually` (resets each grain)
  - `timePeriod.startDate`: must be 1st of a month, ≤3 months in the future
  - `notifications`: named objects `{enabled, operator, threshold, thresholdType: Actual|Forecasted, contactEmails}`. **Threshold = percent of amount** (0.01–1000). Max 5 emails per budget.
- `Forecasted` fires when projected month-end spend crosses the threshold — early warning.
- Whitelist **azure-noreply@microsoft.com** or alert emails land in junk.
- Brand-new subscriptions: Cost Management features can lag up to 48h.
- CLI: `az consumption budget list|delete` (preview). `create` exists but notification support is thin → use Bicep or REST for alerts.

## Bicep / ARM deployment

- Bicep = declarative IaC DSL, compiles to ARM JSON. az CLI auto-installs the compiler on first use.
- **Subscription scope** (`targetScope = 'subscription'`):
  `az deployment sub create --name <label> --location <region> --template-file <file>`
  `--location` only stores deployment metadata — irrelevant for region-less resources. Sub-scope residents: budgets, policy/role assignments, resource groups themselves (a sub-scope template can create RGs and nest modules into them).
- **Resource-group scope** (Bicep's default):
  `az deployment group create --resource-group <rg> --template-file <file>` — no location flag; the RG has one.
- No inline template text — file, URI, or template spec only. File-free routes: per-resource imperative commands (`az group create`, ...) or raw REST via `az rest --method put --url <ARM endpoint> --body '<json>'`.
- Default mode is **Incremental**: re-deploying the same file is idempotent (updates in place) — safe to re-run.

## az CLI auth

- Refresh tokens expire after **90 days idle** (`AADSTS700082`). Plain `az login` can then succeed on the home account yet report "No subscriptions found" — re-auth into the subscription's tenant explicitly:
  `az login --tenant ef7a7f2c-42a8-43f8-90d8-fda9053a8a7a` (tenant of the `VWDeveloper` sub, `ece7f970-...`).
