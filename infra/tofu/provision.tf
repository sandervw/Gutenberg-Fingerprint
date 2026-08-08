# Runs after create; classic OVH VPS images ignore cloud-init.
data "ovh_vps" "gufime" {
  service_name = ovh_vps.gufime.service_name
}

locals {
  vps_ipv4 = [for ip in data.ovh_vps.gufime.ips : split("/", ip)[0] if can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+", ip))][0]
}

resource "terraform_data" "provision" {
  triggers_replace = {
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

# Dagster: two systemd services, Postgres-backed storage.
resource "terraform_data" "dagster" {
  depends_on = [terraform_data.provision]

  triggers_replace = {
    webserver_sha = filesha256("${path.module}/systemd/dagster-webserver.service")
    daemon_sha    = filesha256("${path.module}/systemd/dagster-daemon.service")
    instance_sha  = filesha256("${path.module}/../dagster/dagster.yaml")
  }

  connection {
    type        = "ssh"
    host        = local.vps_ipv4
    user        = "ubuntu"
    private_key = file("~/.ssh/gufime_rsa")
  }

  provisioner "file" {
    source      = "${path.module}/systemd/dagster-webserver.service"
    destination = "/tmp/dagster-webserver.service"
  }

  provisioner "file" {
    source      = "${path.module}/systemd/dagster-daemon.service"
    destination = "/tmp/dagster-daemon.service"
  }

  provisioner "file" {
    source      = "${path.module}/../dagster/dagster.yaml"
    destination = "/tmp/dagster.yaml"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo install -d -o gufime -g gufime /files/gufime/dagster",
      "sudo install -o gufime -g gufime -m 0644 /tmp/dagster.yaml /files/gufime/dagster/dagster.yaml",
      "sudo install -m 0644 /tmp/dagster-webserver.service /etc/systemd/system/dagster-webserver.service",
      "sudo install -m 0644 /tmp/dagster-daemon.service /etc/systemd/system/dagster-daemon.service",
      "sudo systemctl daemon-reload",
      "sudo systemctl enable --now dagster-webserver.service dagster-daemon.service",
    ]
  }
}
