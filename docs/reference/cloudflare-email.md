# Cloudflare Email Sending

Transactional email over Cloudflare's REST API. Used by the Dagster `failure_alert` run-status sensor (`python/dagster/alert.py`).

## Endpoint & auth

```
POST https://api.cloudflare.com/client/v4/accounts/{account_id}/email/sending/send
Authorization: Bearer <API_TOKEN>
Content-Type: application/json
```

- Account id: `954c30f428e0a61f4c66e6a679f51ec0`.
- Token: the shared `~/.config/gufime/cf_token` on the box, carrying the **Send Email** permission.
- `alert.py` reads `CLOUDFLARE_API_TOKEN` if set, else the token file.

## Domain

- `gufime.com` is onboarded to Email Sending (Dashboard → Compute & AI → Email Service), with SPF + DKIM DNS records.
- The `from` address must be `@gufime.com`.

## Request fields

| Field | Notes |
| ----- | ----- |
| `to` | string or string[], max 50 combined with cc/bcc |
| `from` | string, or `{address, name}` object |
| `subject` | required |
| `text` / `html` | at least one; include both |
| `reply_to` | snake_case |

## Response

Success: `{ "success": true, "result": { "delivered": [...], "permanent_bounces": [...], "queued": [...] } }`.

Failure: `{ "success": false, "errors": [{ "code": 1000, "message": "..." }] }`, numeric codes.

Retry 429 and 500 with backoff; 400 and 401 are terminal. Transactional email only.

## Test

```bash
ssh gufime
cd /code/gufime
GUFIME_ALERT_TO=samvanwilligen@gmail.com uv run python -m python.dagster.alert "test"
```

## Source

Cloudflare Email Sending REST reference: https://developers.cloudflare.com/api/resources/email_sending/methods/send
