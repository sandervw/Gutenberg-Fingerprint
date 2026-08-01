#!/usr/bin/env bash
set -euo pipefail

GUFIME_KEY="${1:?ssh public key required}"

apt-get update
apt-get upgrade -y
apt-get install -y postgresql postgresql-client build-essential git curl unattended-upgrades

# gufime user, passwordless sudo, own ssh key
id -u gufime &>/dev/null || useradd -m -s /bin/bash gufime
echo "gufime ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/gufime
chmod 440 /etc/sudoers.d/gufime
install -d -m 700 -o gufime -g gufime /home/gufime/.ssh
echo "$GUFIME_KEY" > /home/gufime/.ssh/authorized_keys
chmod 600 /home/gufime/.ssh/authorized_keys
chown gufime:gufime /home/gufime/.ssh/authorized_keys

cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

# Role, database, schemas. Peer auth over the unix socket.
su - postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='gufime'\"" | grep -q 1 || \
  su - postgres -c "createuser --createdb gufime"
su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='gufime'\"" | grep -q 1 || \
  su - postgres -c "createdb -O gufime gufime"
su - gufime -c "psql -c 'CREATE SCHEMA IF NOT EXISTS bronze; CREATE SCHEMA IF NOT EXISTS raw; CREATE SCHEMA IF NOT EXISTS gold; DROP SCHEMA IF EXISTS public CASCADE;'"

# Node 24 and wrangler for the Evidence build.
curl -fsSL https://deb.nodesource.com/setup_24.x | bash -
apt-get install -y nodejs
npm install -g wrangler

# uv installs to /home/gufime/.local/bin.
su - gufime -c "curl -LsSf https://astral.sh/uv/install.sh | sh"

mkdir -p /files/gufime /code/gufime
chown -R gufime:gufime /files/gufime /code/gufime

# 2 GB swap: the Evidence build peaks near it on a 4 GB box.
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
