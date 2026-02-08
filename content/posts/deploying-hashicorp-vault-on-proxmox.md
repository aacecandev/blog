---
title: "Deploying HashiCorp Vault on Proxmox: A Two-Stage Infrastructure Approach"
date: "2025-11-23"
description: "Deploy a production-ready HashiCorp Vault cluster on Proxmox using OpenTofu. Learn how to automate VM provisioning, configure a 3-node Raft cluster, and manage secrets with SOPS encryption. Part 4 of our Proxmox infrastructure series."
tags: ["proxmox", "vault", "hashicorp", "opentofu", "terraform", "secrets-management", "raft", "docker", "infrastructure", "security"]
---

# Deploying HashiCorp Vault on Proxmox: A Two-Stage Infrastructure Approach

Welcome to Part 4 of our Proxmox infrastructure series! We've [bootstrapped Proxmox with secure automation](./proxmox-bootstrap-automation.md) and [created golden images with Packer](./creating-golden-images-with-packer.md). Now it's time to deploy something essential for managing secrets across your infrastructure: **HashiCorp Vault**.

## Why Vault?

As your infrastructure grows, you'll accumulate secrets everywhere—API keys, database passwords, certificates, SSH keys, and more. Managing these manually becomes:

- **Insecure**: Secrets in plain text files or environment variables
- **Untrackable**: Who accessed what and when?
- **Unmaintainable**: Rotating credentials requires updating dozens of places
- **Risky**: No central revocation when someone leaves or a key is compromised

HashiCorp Vault solves these problems by providing:

- **Centralized Secrets Management**: One place to store, access, and audit all secrets
- **Dynamic Secrets**: Generate credentials on-demand and automatically revoke them
- **Encryption as a Service**: Encrypt/decrypt data without managing keys yourself
- **Fine-Grained Access Control**: Who can access what, when, and from where
- **Audit Logging**: Complete audit trail of every access and operation

## What We're Building

We'll deploy a production-grade Vault cluster with:

- **3-node Vault cluster** with Raft integrated storage (high availability)
- **NGINX load balancer** for a single entry point
- **Auto-unseal monitor** to automatically unseal nodes after restarts
- **Docker Compose orchestration** for easy management
- **Two-stage OpenTofu deployment**:
  1. **Stage 1**: Provision a VM with cloud-init
  2. **Stage 2**: Configure Vault with authentication and secrets engines

This setup is based on the excellent work by [k5yisen](https://github.com/k5yisen/vault-docker-cluster), adapted for Proxmox and integrated into our infrastructure-as-code workflow.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Proxmox VE Host                                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Vault VM (192.168.1.82)                              │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  Docker Compose Stack                           │  │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐        │  │  │
│  │  │  │ Vault-1  │ │ Vault-2  │ │ Vault-3  │        │  │  │
│  │  │  │  (Raft)  │ │  (Raft)  │ │  (Raft)  │        │  │  │
│  │  │  │  :8200   │ │  :8201   │ │  :8202   │        │  │  │
│  │  │  └──────────┘ └──────────┘ └──────────┘        │  │  │
│  │  │       │            │            │               │  │  │
│  │  │       └────────────┴────────────┘               │  │  │
│  │  │                    │                            │  │  │
│  │  │         ┌──────────▼──────────┐                │  │  │
│  │  │         │  NGINX Load Balancer│                │  │  │
│  │  │         │    :8200 (exposed)  │                │  │  │
│  │  │         └─────────────────────┘                │  │  │
│  │  │         ┌─────────────────────┐                │  │  │
│  │  │         │  Auto-unseal Monitor│                │  │  │
│  │  │         └─────────────────────┘                │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

Before starting, ensure you have:

- **Proxmox VE 8.0+** with the bootstrap automation user from [Part 2](./proxmox-bootstrap-automation.md)
- **Golden image template** (VM ID 100) from [Part 3](./creating-golden-images-with-packer.md)
- **OpenTofu** installed locally
- **SOPS and age** for secrets encryption
- **SSH access** to your Proxmox host

## Project Setup

### Directory Structure

```
vault-docker-cluster/
├── opentofu-vm/              # Stage 1: VM provisioning
│   ├── vm.tf
│   ├── providers.tf
│   ├── variables.tf
│   ├── terraform.tfvars      # Encrypted with SOPS
│   └── vault-user-data.yaml
│
├── opentofu-vault/           # Stage 2: Vault configuration
│   ├── providers.tf
│   ├── auth.tf
│   ├── kv.tf
│   ├── policies.tf
│   └── terraform.tfvars      # Encrypted with SOPS
│
├── vault/                    # Deployed to VM
│   ├── docker-compose.yaml
│   ├── Dockerfile.vault
│   ├── init-and-generate-unseal.sh
│   ├── auto-unseal-monitor.sh
│   ├── start.sh
│   ├── vault-1/config/
│   ├── vault-2/config/
│   ├── vault-3/config/
│   └── nginx/
│
├── .envrc                    # Encrypted with SOPS
├── .sops.yaml
└── age.agekey               # Your encryption key
```

### Setting Up Encryption

First, generate an age key for encrypting sensitive files:

```bash
# Generate encryption key
age-keygen -o age.agekey

# Example output:
# Public key: <AGE_PUBLIC_KEY>
```

Create `.sops.yaml` with your public key:

```yaml
creation_rules:
  - path_regex: .*/terraform\.tfvars$
    age: <AGE_PUBLIC_KEY>
  - path_regex: .*\.envrc$
    age: <AGE_PUBLIC_KEY>
```

Set the environment variable:

```bash
export SOPS_AGE_KEY_FILE=./age.agekey
# Or add to .envrc and use direnv
```

## Stage 1: Provisioning the Vault VM

Stage 1 uses OpenTofu to create a VM from our golden image and prepare it for Vault deployment.

### What Cloud-init Does

The `vault-user-data.yaml` cloud-init configuration:

1. **Installs Docker and Docker Compose** using the official installation script
2. **Configures system tuning** for Vault (file descriptors, max_map_count)
3. **Uploads Vault cluster files** as a base64-encoded tar.gz archive
4. **Enables qemu-guest-agent** for better Proxmox integration
5. **Sets up SSH access** with your public key

Here's a snippet of the cloud-init configuration:

```yaml
#cloud-config
hostname: vault
fqdn: vault.local

packages:
  - curl
  - wget
  - git
  - jq
  - net-tools
  - ca-certificates
  - qemu-guest-agent

write_files:
  - path: /etc/sysctl.d/99-vault.conf
    content: |
      vm.max_map_count=262144
      fs.file-max=65536

  - path: /opt/vault/vault-archive.tar.gz
    encoding: b64
    content: ${vault_archive_b64}

runcmd:
  # Install Docker
  - curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  - sh /tmp/get-docker.sh
  - usermod -aG docker ubuntu

  # Install Docker Compose
  - mkdir -p /usr/local/lib/docker/cli-plugins
  - curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" -o /usr/local/lib/docker/cli-plugins/docker-compose
  - chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
```

### Configure and Deploy

Create `opentofu-vm/terraform.tfvars` from the example:

```hcl
proxmox_endpoint  = "https://192.168.1.200:8006/api2/json"
proxmox_api_token = "tofu@pve!deployment=c723f2f4-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

proxmox_node   = "pve-1"
vm_name        = "vault"
vm_id          = 8200  # Port 8200 -> VM ID 8200 for easy recall
template_vm_id = "100"

network_config = {
  bridge = "vmbr0"
  model  = "virtio"
}

initialization = {
  datastore_id = "local-zfs"
  ip_config = {
    ipv4 = {
      address = "192.168.1.82/24"
      gateway = "192.168.1.1"
    }
  }
  user_account = {
    keys     = ["ssh-ed25519 AAAAC3NzaC1... your-key"]
    username = "ubuntu"
  }
}
```

Encrypt the configuration:

```bash
# Encrypt before committing
sops --encrypt --in-place opentofu-vm/terraform.tfvars
```

Deploy the VM:

```bash
cd opentofu-vm

# Initialize OpenTofu
tofu init

# Preview changes
tofu plan

# Apply (decrypt first if needed)
sops --decrypt --in-place terraform.tfvars
tofu apply
sops --encrypt --in-place terraform.tfvars
```

### Wait for Cloud-init

SSH into the VM and wait for cloud-init to complete:

```bash
ssh ubuntu@192.168.1.82

# Check cloud-init status
cloud-init status --wait

# Expected output:
# status: done
```

This usually takes 3-5 minutes for Docker installation and configuration.

## Initializing the Vault Cluster

Once cloud-init completes, we'll manually initialize Vault on the VM. This is a **one-time operation** that generates the root token and unseal keys.

### Extract and Start Vault

```bash
# On the VM
cd /opt/vault
tar -xzf vault-archive.tar.gz
cd vault  # Adjust path if extracted differently

# Run the start script
./start.sh
```

The `start.sh` script performs these operations:

```bash
#!/bin/bash

export VAULT_ADDR='http://127.0.0.1:8200'
export KEY_SHARES=5
export KEY_THRESHOLD=3

# Build custom Vault 1.20 image
docker build -f Dockerfile.vault -t vaultdockercluster:1.20 .

# Start all containers
docker compose up -d

# Initialize vault-1 and generate unseal keys
./init-and-generate-unseal.sh

# Unseal and join all nodes
docker compose exec vault-1 sh /vault/config/unseal.sh && \
docker compose exec vault-2 sh -c "export VAULT_ADDR=${VAULT_ADDR} && vault operator raft join http://vault-1:8200" && \
docker compose exec vault-2 sh /vault/config/unseal.sh && \
docker compose exec vault-3 sh -c "export VAULT_ADDR=${VAULT_ADDR} && vault operator raft join http://vault-1:8200" && \
docker compose exec vault-3 sh /vault/config/unseal.sh
```

### Understanding Vault Initialization

The initialization process creates:

1. **Unseal Keys** (5 keys, threshold 3): Used to unseal Vault after restarts
2. **Root Token**: The master token with full privileges
3. **Credentials File**: `vault-credentials-YYYYMMDD-HHMMSS.md` with all keys and token

**⚠️ Critical Security Note**: The unseal keys and root token provide complete access to Vault. In production:

- Store them in a secure vault (not on the VM!)
- Use separate key holders (Shamir's Secret Sharing)
- Consider auto-unseal with cloud KMS
- Revoke the root token after initial setup

### Secure the Credentials

```bash
# On the VM - view and copy credentials
cat vault-credentials-*.md

# Copy the output to your password manager or secure notes
# Then delete the file
rm vault-credentials-*.md
```

The credentials file looks like this:

```markdown
# Vault Initialization - 2025-11-23-025556

## Root Token
<vault-root-token>

## Unseal Keys
Unseal Key 1: [REDACTED]
Unseal Key 2: [REDACTED]
Unseal Key 3: [REDACTED]
Unseal Key 4: [REDACTED]
Unseal Key 5: [REDACTED]

Initial Root Token: <vault-root-token>

Vault initialized with 5 key shares and a key threshold of 3. Please securely
distribute the key shares printed above. When Vault is re-sealed, restarted, or
stopped, you must supply at least 3 of these keys to unseal it before it can
start servicing requests.
```

### Verify the Cluster

```bash
# Check all containers are running
docker compose ps

# Should show 5 containers:
# - vault-1 (Up)
# - vault-2 (Up)
# - vault-3 (Up)
# - load-balancer (Up)
# - vault-unsealer (Up)

# Verify Vault status
export VAULT_ADDR='http://127.0.0.1:8200'
curl -s $VAULT_ADDR/v1/sys/health | jq

# Check Raft cluster membership
export VAULT_TOKEN='<YOUR_VAULT_TOKEN>'
docker compose exec vault-1 vault operator raft list-peers
```

Expected output:

```json
{
  "initialized": true,
  "sealed": false,
  "standby": false,
  "performance_standby": false,
  "replication_performance_mode": "disabled",
  "replication_dr_mode": "disabled",
  "server_time_utc": 1732324556,
  "version": "1.20.0",
  "cluster_name": "vault-cluster-abc123",
  "cluster_id": "d4c5b6a7-8e9f-0a1b-2c3d-4e5f6a7b8c9d"
}
```

## Stage 2: Configuring Vault

Now that Vault is running, we'll configure it with authentication backends and secrets engines using OpenTofu.

### Update Your Environment

First, add the Vault token to `.envrc`:

```bash
#!/bin/bash

export VAULT_ADDR='http://192.168.1.82:8200'
export VAULT_TOKEN='<YOUR_VAULT_TOKEN>'  # From initialization
export KEY_SHARES=5
export KEY_THRESHOLD=3
export SOPS_AGE_KEY_FILE=./age.agekey
```

Encrypt it:

```bash
sops --encrypt --in-place .envrc
```

Load the environment (decrypt temporarily):

```bash
sops --decrypt --in-place .envrc
source .envrc
sops --encrypt --in-place .envrc
```

### Configure Authentication and Secrets

Create `opentofu-vault/terraform.tfvars`:

```hcl
admin_password  = "change-this-secure-admin-password"
kvuser_password = "change-this-secure-kvuser-password"
```

Encrypt it:

```bash
sops --encrypt --in-place opentofu-vault/terraform.tfvars
```

The OpenTofu configuration in `auth.tf` creates:

```hcl
resource "vault_auth_backend" "userpass" {
  type = "userpass"
  path = "userpass"
  tune {
    default_lease_ttl = "2h"
    max_lease_ttl     = "24h"
  }
}

resource "vault_generic_endpoint" "admin" {
  path = "auth/userpass/users/admin"
  data_json = jsonencode({
    password       = var.admin_password
    token_policies = ["admin"]
    token_ttl      = "2h"
    token_max_ttl  = "24h"
  })
}

resource "vault_generic_endpoint" "kvuser" {
  path = "auth/userpass/users/kvuser"
  data_json = jsonencode({
    password       = var.kvuser_password
    token_policies = ["kvuser", "update_userpass"]
    token_ttl      = "2h"
    token_max_ttl  = "24h"
  })
}
```

And `kv.tf` mounts a KV v2 secrets engine:

```hcl
resource "vault_mount" "kvv2" {
  path        = "kvv2"
  type        = "kv"
  description = "KV version 2 secrets engine"
  options = {
    version = "2"
  }
}
```

### Deploy the Configuration

```bash
cd opentofu-vault

tofu init

# Decrypt, apply, re-encrypt
sops --decrypt --in-place terraform.tfvars
tofu apply
sops --encrypt --in-place terraform.tfvars
```

## Using Your Vault Cluster

### Accessing the UI

Navigate to `http://192.168.1.82:8200/ui` in your browser.

Login options:

- **Method**: Userpass
- **Username**: `admin`
- **Password**: (from terraform.tfvars)

Or use the root token for initial setup.

### CLI Access

```bash
export VAULT_ADDR='http://192.168.1.82:8200'

# Login with userpass
vault login -method=userpass username=admin

# Store a secret
vault kv put kvv2/myapp/database username=dbuser password=dbpass

# Read a secret
vault kv get kvv2/myapp/database

# List secrets
vault kv list kvv2/myapp
```

### Programmatic Access

From your applications:

```python
import hvac

# Initialize client
client = hvac.Client(url='http://192.168.1.82:8200')

# Authenticate
client.auth.userpass.login(
    username='kvuser',
    password='your-password'
)

# Read secret
secret = client.secrets.kv.v2.read_secret_version(
    path='myapp/database',
    mount_point='kvv2'
)

print(secret['data']['data']['password'])
```

## Understanding Vault Concepts

### Raft Integrated Storage

Instead of using Consul or an external database, Vault uses **Raft consensus** for:

- **Leader Election**: One node is elected leader, others are followers
- **Data Replication**: All writes go to the leader, replicated to followers
- **High Availability**: If the leader fails, a new one is elected automatically
- **Simplified Operations**: No external dependencies

Check cluster status:

```bash
vault operator raft list-peers

# Output:
# Node       Address             State       Voter
# vault-1    vault-1:8201        leader      true
# vault-2    vault-2:8201        follower    true
# vault-3    vault-3:8201        follower    true
```

### Sealing and Unsealing

Vault starts in a **sealed** state. Sealing means:

- Data is encrypted on disk
- Vault cannot decrypt or read any secrets
- All API requests (except unseal) are rejected

To unseal, you provide **threshold** number of unseal keys (3 out of 5 in our setup).

Our `vault-unsealer` container automatically unseals nodes when they restart:

```bash
# Check unsealer logs
docker compose logs -f vault-unsealer

# Manually unseal if needed
vault operator unseal  # Enter 3 different unseal keys
```

### Auto-Unseal Monitor

The `auto-unseal-monitor.sh` script runs in a container and:

1. Polls each Vault node every 30 seconds
2. Checks if the node is sealed
3. Automatically runs the unseal script if sealed
4. Logs all operations with timestamps

This is convenient for labs but **NOT recommended for production**. Use cloud KMS auto-unseal instead (AWS KMS, Azure Key Vault, GCP Cloud KMS).

## Operations and Maintenance

### Checking Cluster Health

```bash
# On the VM
cd /opt/vault

# Container status
docker compose ps

# Vault status for each node
docker compose exec vault-1 vault status
docker compose exec vault-2 vault status
docker compose exec vault-3 vault status

# Raft peers
docker compose exec vault-1 vault operator raft list-peers

# Load balancer health
curl http://localhost:8200/health
```

### Viewing Logs

```bash
# All logs
docker compose logs -f

# Specific service
docker compose logs -f vault-1
docker compose logs -f load-balancer
docker compose logs -f vault-unsealer

# Follow logs with timestamps
docker compose logs -f --timestamps vault-1
```

### Restarting the Cluster

```bash
# Graceful restart
docker compose restart

# Or stop and start
docker compose down
docker compose up -d

# Check status after restart
docker compose ps
```

The auto-unseal monitor will automatically unseal the nodes within 30 seconds.

### Backing Up Vault Data

Raft snapshots capture the entire Vault state:

```bash
# Create snapshot
vault operator raft snapshot save /tmp/vault-backup.snap

# Download to local machine
scp ubuntu@192.168.1.82:/tmp/vault-backup.snap ./vault-backup-$(date +%Y%m%d).snap

# Store in secure location (encrypted cloud storage, etc.)
```

### Restoring from Backup

```bash
# Upload snapshot
scp ./vault-backup-20251123.snap ubuntu@192.168.1.82:/tmp/

# Restore on the VM
vault operator raft snapshot restore /tmp/vault-backup-20251123.snap
```

## Security Hardening for Production

Our lab setup is **HTTP-only and not hardened**. For production, implement:

### 1. Enable TLS/HTTPS

Generate certificates and update `vault-*/config/vault.hcl`:

```hcl
listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_cert_file = "/vault/config/vault.crt"
  tls_key_file  = "/vault/config/vault.key"
}
```

### 2. Use Auto-Unseal with Cloud KMS

Replace Shamir unsealing with AWS KMS:

```hcl
seal "awskms" {
  region     = "us-east-1"
  kms_key_id = "alias/vault-unseal-key"
}
```

### 3. Implement Proper RBAC

Create policies for each use case instead of using the root token:

```hcl
# Read-only policy
path "kvv2/data/myapp/*" {
  capabilities = ["read", "list"]
}

# Write policy
path "kvv2/data/myapp/*" {
  capabilities = ["create", "update", "delete"]
}
```

### 4. Enable Audit Logging

```bash
vault audit enable file file_path=/vault/logs/audit.log
```

### 5. Firewall Rules

Restrict access to Vault:

```bash
# Only allow from application subnet
ufw allow from 192.168.1.0/24 to any port 8200
ufw deny 8200
```

### 6. Regular Snapshots

Automate Raft snapshots with a cron job:

```bash
# Daily backup at 2 AM
0 2 * * * /usr/local/bin/vault-backup.sh
```

### 7. Monitor and Alert

Set up monitoring for:

- Vault seal status
- Raft cluster health
- Failed authentication attempts
- Certificate expiration
- Snapshot success/failure

## Troubleshooting

### Containers Won't Start

```bash
# Check Docker service
systemctl status docker

# View Docker daemon logs
journalctl -u docker -f

# Check container logs
docker compose logs vault-1
```

### Can't Connect to Vault from Local Machine

```bash
# Verify Vault is listening
ssh ubuntu@192.168.1.82 "curl -s http://127.0.0.1:8200/v1/sys/health"

# Check firewall
ssh ubuntu@192.168.1.82 "sudo ufw status"

# Test connectivity
telnet 192.168.1.82 8200
```

### Node is Sealed After Restart

Check the auto-unseal monitor:

```bash
docker compose logs vault-unsealer

# Manually unseal if needed
docker compose exec vault-1 sh /vault/config/unseal.sh
```

### OpenTofu Apply Fails in Stage 2

```bash
# Verify environment variables
echo $VAULT_ADDR
echo $VAULT_TOKEN

# Test connection
curl -H "X-Vault-Token: $VAULT_TOKEN" $VAULT_ADDR/v1/sys/health

# Check if Vault is sealed
vault status
```

## What's Next?

Now that you have Vault running, you can:

1. **Integrate with Applications**: Use Vault's SDKs to fetch secrets dynamically
2. **Set Up Dynamic Secrets**: Generate database credentials on-demand
3. **Enable Additional Auth Methods**: LDAP, GitHub, JWT, Kubernetes
4. **Configure PKI**: Use Vault as a Certificate Authority
5. **Implement Encryption as a Service**: Encrypt/decrypt data without managing keys

In the next post, we'll integrate Vault with our blog deployment, using it to securely manage:

- Database passwords
- API keys
- TLS certificates
- SSH keys for deployments

## Repository

The complete code for this deployment is available in my infrastructure repository:

```
infra/proxmox/bootstrap/vault-docker-cluster/
```

Remember to use SOPS encryption for all sensitive files before committing!

## Acknowledgments

This Vault cluster setup is based on the excellent work by [k5yisen](https://github.com/k5yisen/vault-docker-cluster). The original repository provides a complete Docker Compose setup with auto-unsealing and NGINX load balancing. I've adapted it for Proxmox deployment and integrated it with OpenTofu for infrastructure-as-code management.

## Conclusion

You now have a production-grade Vault cluster running on Proxmox! While this setup is suitable for labs and development, remember to implement the security hardening steps for production use.

The two-stage deployment approach separates infrastructure provisioning from application configuration, making it easy to rebuild or scale your Vault cluster. Using SOPS encryption ensures that your credentials remain secure even in version control.

In the next post, we'll integrate Vault into our CI/CD pipeline and use it to securely manage secrets across our entire infrastructure.

Happy secret managing! 🔐
