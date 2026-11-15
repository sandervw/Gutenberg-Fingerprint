# Deploys and operations

## What ships when

| Event | Result |
|---|---|
| Merge to `main` | `.github/workflows/deploy.yml` syncs `/code/gufime` on the box, runs `dbt parse --target postgres`, and restarts Dagster |
| Nightly run with new works | The `site` asset builds Evidence on the box and runs `wrangler pages deploy` to gufime.com |

A merge goes live on the box within minutes. The site changes on the next run with new works, or on *Materialize all*.

## The box

OVH VPS-1 (2 vCore, 4 GB, 40 GB NVMe), `ssh gufime`. Code at `/code/gufime`, data at `/files/gufime/`. Two systemd units serve Dagster: `dagster-webserver` on `127.0.0.1:3000` and `dagster-daemon`. The UI is at `dagster.gufime.com` behind a Cloudflare Tunnel and Access. Unattended security upgrades, Postgres on the local socket, 6 GB swap.

## Infra as code

`infra/tofu/` (OpenTofu, OVH and Cloudflare providers) orders the box and declares the R2 bucket. `provision.sh` installs Postgres with the four schemas and peer auth, `uv`, Node 24, `wrangler`, `cloudflared`, and the folders. `provision.tf` installs the Dagster units and the tunnel service. `tofu apply` needs the CEO's yes.

## Backups

On changed nights `postgres_backup` writes `pg_dump -Fc` to R2 `gufime-backup/postgres/gufime.dump`, then `corpus_backup` tars `/files/gufime/` into 250 MB parts under `corpus/` with a sha256 `corpus.manifest` uploaded last. Keys are latest-only. Restore: fetch the parts the manifest lists, `cat corpus.tar.gz.* | tar -xz`, and `pg_restore -d gufime`.

## Credentials

| Credential | Lives in | Used for |
|---|---|---|
| Box SSH key | Actions secret `GUFIME_SSH_KEY`; `~/.ssh/gufime_rsa` locally | Deploy hook |
| Cloudflare API token | `~/.config/gufime/cf_token` on the box | Pages, R2, Email Sending |
| Cloudflare Tunnel token | `cloudflared` on the box | Dagster UI |
| OVH and Cloudflare tokens for OpenTofu | `infra/tofu/` tfvars on the laptop | `tofu apply` |

## Cost

About $5/month for the box. GitHub Actions, Cloudflare Pages, Tunnel, Access, and R2 sit in free tiers.
