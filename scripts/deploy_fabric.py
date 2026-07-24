"""Publish fabric/ item definitions to the Fabric workspace with fabric-cicd.

    uv run python scripts/deploy_fabric.py              # create/update items
    uv run python scripts/deploy_fabric.py --unpublish  # also delete orphans

The capacity must be Active. A paused capacity answers item-definition calls
with NotFound:

    az resource invoke-action --ids <capacity-resource-id> --action resume

Auth defaults to the signed-in Azure CLI user, which has to be the Entra
account gbfingerprint@…onmicrosoft.com - the personal MSA that owns the
subscription is not a valid Fabric identity. `--auth spn` uses the service
principal in .env (AZURE_appId / AZURE_password / AZURE_tenant) instead, for
unattended runs.

Workspace Contributor is enough for every item except pl_nightly: publishing a
pipeline also requires access to the connections its activities call, granted
per connection under Manage connections and gateways. The .env SPN has the
workspace role but not the connections, so it publishes everything but the
pipeline.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from azure.identity import AzureCliCredential, ClientSecretCredential
from fabric_cicd import FabricWorkspace, publish_all_items, unpublish_all_orphan_items

REPO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_DIRECTORY = REPO_ROOT / "fabric"

WORKSPACE_ID = "bfad3948-6e3b-4eeb-8ee1-485e0f47c87b"

# Selects which branch of parameter.yml's replace_value maps to use.
ENVIRONMENT = "PROD"

# Ordering is fabric-cicd's job, not ours: it sequences lakehouses before
# notebooks before pipelines. Warehouse is deliberately absent - wh_gold has no
# item definition to deploy, and listing the type here would make --unpublish
# delete it as an orphan.
ITEM_TYPE_IN_SCOPE = ["Lakehouse", "Notebook", "DataBuildToolJob", "DataPipeline"]


def load_dotenv(path: Path) -> None:
    """Read KEY=value lines from .env without pulling in python-dotenv. Real
    environment variables win, so CI can override the local file."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def build_credential(auth: str):
    if auth == "cli":
        return AzureCliCredential()

    load_dotenv(REPO_ROOT / ".env")
    app_id = os.environ.get("AZURE_appId")
    secret = os.environ.get("AZURE_password")
    tenant = os.environ.get("AZURE_tenant")
    if not (app_id and secret and tenant):
        msg = "AZURE_appId / AZURE_password / AZURE_tenant must all be set for --auth spn"
        raise SystemExit(msg)
    return ClientSecretCredential(tenant_id=tenant, client_id=app_id, client_secret=secret)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--unpublish",
        action="store_true",
        help="delete items of the in-scope types that are absent from fabric/",
    )
    parser.add_argument(
        "--auth",
        choices=("cli", "spn"),
        default="cli",
        help="identity to deploy as (default: the signed-in Azure CLI user)",
    )
    args = parser.parse_args()

    workspace = FabricWorkspace(
        workspace_id=WORKSPACE_ID,
        environment=ENVIRONMENT,
        repository_directory=str(REPOSITORY_DIRECTORY),
        item_type_in_scope=ITEM_TYPE_IN_SCOPE,
        token_credential=build_credential(args.auth),
    )

    publish_all_items(workspace)
    if args.unpublish:
        unpublish_all_orphan_items(workspace)


if __name__ == "__main__":
    main()
