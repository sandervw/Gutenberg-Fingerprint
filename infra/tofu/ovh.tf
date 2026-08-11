provider "ovh" {
  endpoint           = var.ovh_endpoint
  application_key    = var.ovh_application_key
  application_secret = var.ovh_application_secret
  consumer_key       = var.ovh_consumer_key
}

variable "ovh_endpoint" {
  type    = string
  default = "ovh-us"
}

variable "ovh_application_key" {
  type      = string
  sensitive = true
}

variable "ovh_application_secret" {
  type      = string
  sensitive = true
}

variable "ovh_consumer_key" {
  type      = string
  sensitive = true
}

data "ovh_me" "account" {}

# VPS-1 2027: 2 vCore / 4GB RAM / 40GB NVMe, US-WEST-OR (Hillsboro).
resource "ovh_vps" "gufime" {
  display_name = "gufime"

  image_id       = "ff8500f7-407c-4e80-9db6-1b4ad242705f" # Ubuntu 24.04
  public_ssh_key = trimspace(file("~/.ssh/gufime_rsa.pub"))

  ovh_subsidiary = data.ovh_me.account.ovh_subsidiary

  plan = [
    {
      duration     = "P1M"
      plan_code    = "vps-2027-model1"
      pricing_mode = "default"

      configuration = [
        {
          label = "vps_datacenter"
          value = "US-WEST-OR"
        },
        {
          label = "vps_os"
          value = "Ubuntu 24.04"
        }
      ]
    }
  ]

  # Both mandatory addon families on this plan line.
  plan_option = [
    {
      duration     = "P1M"
      plan_code    = "option-storage-local-2027-model1"
      pricing_mode = "default"
      quantity     = 1
    },
    {
      duration     = "P1M"
      plan_code    = "option-auto-backup-2027-1-model1"
      pricing_mode = "default"
      quantity     = 1
    }
  ]

  # Order-time fields; unreadable after creation, don't force replacement.
  lifecycle {
    ignore_changes = [image_id, ovh_subsidiary, plan, plan_option, public_ssh_key]
  }
}

output "vps_service_name" {
  value = ovh_vps.gufime.service_name
}
