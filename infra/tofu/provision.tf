# Runs after create; classic OVH VPS images ignore cloud-init.
data "ovh_vps" "gufime" {
  service_name = ovh_vps.gufime.service_name
}

locals {
  vps_ipv4 = [for ip in data.ovh_vps.gufime.ips : split("/", ip)[0] if can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+", ip))][0]
}

resource "null_resource" "provision" {
  triggers = {
    script_sha = filesha256("${path.module}/scripts/provision.sh")
  }

  connection {
    type        = "ssh"
    host        = local.vps_ipv4
    user        = "ubuntu"
    private_key = file("~/.ssh/gufime_rsa")
  }

  provisioner "file" {
    source      = "${path.module}/scripts/provision.sh"
    destination = "/tmp/provision.sh"
  }

  provisioner "remote-exec" {
    inline = [
      "chmod +x /tmp/provision.sh",
      "sudo /tmp/provision.sh '${trimspace(file("~/.ssh/gufime_rsa.pub"))}'",
    ]
  }
}
