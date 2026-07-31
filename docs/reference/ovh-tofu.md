# OVH + OpenTofu

## `ovh_vps` resource

- Orders a classic VPS-1/VPS-2 line server.
- Account needs a default payment method (SEPA direct debit) set in the Control Panel or via `/me/payment/method` before apply.
- Auth: `application_key` + `application_secret` + `consumer_key` from the [US token page](https://api.us.ovhcloud.com/createToken/?GET=/*&POST=/*&PUT=/*&DELETE=/*). Endpoint `ovh-us` for US accounts, `ovh-eu` for EU.
- `plan.configuration` needs `vps_datacenter` and `vps_os` keys from the [VPS catalog](https://us.api.ovhcloud.com/1.0/order/catalog/public/vps?ovhSubsidiary=US), unauthenticated GET. `plan_code` is the subsidiary-specific SKU, not a stable vCPU/RAM/disk suffix — match on the product `description` field instead.
- `vps-2027-model1` = "VPS-1 2027", 2 vCore/4GB/40GB NVMe, matches OVH's console default price. Has US datacenters (`US-EAST-VA`, `US-WEST-OR`), unlike the older `2025-model*` line.
- This plan's `storage` and `automatedBackup` addon families are mandatory, not optional. Must add both as `plan_option` entries or the order is incomplete. Storage is free; backup is $0.50-1.40/mo.
- `plan_option` entries need a `quantity` field. `plan` itself doesn't.
- `do_not_send_password` never round-trips through this provider version, set or unset — apply always reports it inconsistent. Leave it out of config entirely. First apply lands the resource tainted from this; `tofu untaint` after confirming the VPS is actually running.

## Bootstrap

- Classic VPS has no cloud-init / user-data hook ([infrastructure-roadmap#383](https://github.com/ovh/infrastructure-roadmap/issues/383)).
- `public_ssh_key` at create time requires `image_id` too — the provider posts both to `/vps/{serviceName}/rebuild` after ordering. But `image_id` values only list via `/vps/{serviceName}/images/available`, which needs a `serviceName` that doesn't exist until after the first apply.
- Simplest path: order with no `public_ssh_key`/`image_id` (OVH emails a root password). One manual password login to add our own key and lock down sshd. Then `provisioner "remote-exec"` for the rest, keyed off `ovh_vps` service_name.
