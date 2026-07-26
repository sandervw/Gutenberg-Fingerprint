# Azure (non-Fabric)

## Budgets (`Microsoft.Consumption/budgets`, API 2023-11-01)

- Alert-only; never blocks spend.
- `gutenberg-fingerprint-monthly`: $50/mo, 50/90% Actual + 100% Forecasted → sam.vanwilligen@gmail.com; `infra/budget.bicep`.
- `threshold` = percent (0.01-1000); max 5 emails; `startDate` = 1st of month, ≤3 months out.
- Whitelist azure-noreply@microsoft.com.
- New subscriptions lag 48h.
- `az consumption budget create` lacks notifications; use Bicep/REST.

## Auth

- `AADSTS700082` after 90 days idle; `az login` then reports "No subscriptions found".
- `az login --tenant ef7a7f2c-42a8-43f8-90d8-fda9053a8a7a` (VWDeveloper sub `ece7f970-...`).
