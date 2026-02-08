---
title: "Bootstrapping Proxmox for Secure Infrastructure Automation"
date: "2025-11-19"
description: "Learn how to bootstrap a Proxmox environment with dedicated automation users, secure token management, and encrypted secrets using SOPS and age. Part 2 of deploying your blog on Proxmox."
tags: ["proxmox", "infrastructure", "terraform", "opentofu", "security", "devops"]
---

# Bootstrapping Proxmox for Secure Infrastructure Automation

Welcome back to our series on deploying your own blog on Proxmox! In this post, we're diving into a critical foundation piece: setting up your Proxmox environment for automated infrastructure management.

## The Problem: Don't Use Root for Everything

When you first set up Proxmox, you might be tempted to use your root credentials for everything—including your infrastructure-as-code deployments. This is a security anti-pattern for several reasons:

- **Over-privileged access**: Your automation doesn't need full cluster admin rights
- **Credential sprawl**: Root credentials shouldn't be scattered across CI/CD systems
- **Audit trail**: It's difficult to distinguish between human actions and automation
- **Blast radius**: If credentials are compromised, an attacker has complete control

The solution? Create a dedicated automation user with exactly the permissions it needs—nothing more, nothing less.

## What We're Building

We'll use OpenTofu (an open-source Terraform alternative) to bootstrap our Proxmox environment with:

1. **Custom Role** (`tofu`): A role with scoped permissions for VM and storage management
2. **Automation User** (`tofu@pve`): A dedicated user assigned to this role
3. **API Token**: A secure token for programmatic access
4. **Operations Group**: For organizing automation accounts
5. **Base Images**: Pre-downloaded Ubuntu 24.04.3 LTS ISO for future VM deployments

This bootstrap configuration is meant to be run **once** with root credentials. After that, all future infrastructure changes use the dedicated `tofu` user token.

## Repository Structure

Here's what the bootstrap repository contains:

```
infra/proxmox/bootstrap/users/
├── providers.tf              # Terraform provider configuration
├── variables.tf              # Input variable definitions
├── users-tofu.tf            # Main resources (user, role, token)
├── groups.tf                # Group definitions
├── images.tf                # ISO downloads
├── outputs.tf               # Token and ID outputs
├── terraform.tfvars         # Encrypted secrets (SOPS)
├── terraform.tfvars.example # Template for configuration
├── age.agekey              # Age encryption private key
└── README.md               # Documentation
```

## Security First: SOPS and age Encryption

Before we get into the Terraform code, let's talk about secrets management. We're using two tools to keep our credentials safe:

### age: Modern Encryption

[age](https://github.com/FiloSottile/age) is a simple, modern file encryption tool. Think of it as a replacement for GPG, but designed to be easier to use and harder to misuse.

```bash
# Generate a key pair
age-keygen -o age.agekey

# Your public key (recipient) is shown in the output
# <AGE_PUBLIC_KEY>
```

The private key stays on your machine (and in your repository if it's private). The public key is used by SOPS to encrypt files.

### SOPS: Secrets Management

[SOPS](https://github.com/mozilla/sops) (Secrets OPerationS) is Mozilla's tool for encrypting structured data files. Instead of encrypting entire files, SOPS encrypts only the values in JSON/YAML files, leaving keys visible for easier Git diffs.

Our `terraform.tfvars` file is encrypted with SOPS:

```json
{
  "data": "ENC[AES256_GCM,data:xJnrZXT2...",
  "sops": {
    "age": [
      {
        "recipient": "<AGE_PUBLIC_KEY>",
        "enc": "-----BEGIN AGE ENCRYPTED FILE-----\n..."
      }
    ],
    "lastmodified": "2025-11-19T19:55:32Z"
  }
}
```

To decrypt and use it:

```bash
# View the contents
sops -d terraform.tfvars

# Edit in place
sops terraform.tfvars

# OpenTofu/Terraform automatically decrypts via the SOPS provider
tofu plan
```

The SOPS provider in our `providers.tf` handles decryption transparently during Terraform operations.

## The Bootstrap Process

### Step 1: Configure Your Environment

Start by copying the example configuration:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Create an age key if you don't have one:

```bash
age-keygen -o age.agekey
```

Edit the configuration with your Proxmox details:

```hcl
endpoint  = "https://your-proxmox.example.com:8006/"
api_token = "root@pam!bootstrap=your-root-token-here"
realm     = "pve-1"
```

Encrypt it with SOPS:

```bash
sops -e -i --age $(grep "public key:" age.agekey | cut -d: -f2 | tr -d ' ') terraform.tfvars
```

### Step 2: Initialize and Apply

```bash
# Initialize Terraform providers
tofu init

# Preview changes
tofu plan

# Apply the configuration
tofu apply
```

The bootstrap process creates:

1. **A custom role** with these permissions:
   - Datastore operations (allocate space, store templates)
   - VM lifecycle (create, clone, configure, power management)
   - System operations (audit, modify - needed for ISO downloads)
   - Network access (SDN)
   - Guest agent queries

2. **A dedicated user** with:
   - Root-level ACL (propagated to all resources)
   - Storage-specific ACLs for each datastore
   - Association with the operations group

3. **An API token** that:
   - Inherits all user permissions
   - Optionally expires at a specified date
   - Can be rotated without recreating the user

### Step 3: Retrieve Your Token

After successful deployment, get your new automation token:

```bash
tofu output -raw tofu__api_token
```

This outputs the complete token in the format:

```
tofu@pve!deployment=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Store this securely—you'll use it for all future infrastructure deployments.

## Using the Token

Now that you have a dedicated automation token, use it in your infrastructure code:

```hcl
provider "proxmox" {
  endpoint  = "https://your-proxmox.example.com:8006/"
  api_token = "tofu@pve!deployment=your-token-secret"
  insecure  = true
}
```

Or set it as an environment variable:

```bash
export PROXMOX_VE_API_TOKEN=$(tofu output -raw tofu__api_token)
```

## What Gets Downloaded

The bootstrap also downloads Ubuntu 24.04.3 LTS Server ISO to your local datastore. This provides a verified base image for future VM deployments:

```hcl
resource "proxmox_virtual_environment_download_file" "ubuntu_24_04_3_live_server_amd64_iso" {
  content_type       = "iso"
  datastore_id       = "local"
  node_name          = "pve-1"
  url                = "https://releases.ubuntu.com/24.04/ubuntu-24.04.3-live-server-amd64.iso"
  checksum           = "c3514bf0056180d09376462a7a1b4f213c1d6e8ea67fae5c25099c6fd3d8274b"
  checksum_algorithm = "sha256"
}
```

The checksum verification ensures you get an authentic image.

## Security Considerations

### What the tofu Role Can Do

The `tofu` role is carefully scoped:

- ✅ Create and manage VMs
- ✅ Allocate storage and create disks
- ✅ Download ISOs
- ✅ Configure networking
- ✅ Access VM console (for debugging)

### What it Cannot Do

- ❌ Create or modify users
- ❌ Change cluster configuration
- ❌ Access other users' VMs
- ❌ Modify Proxmox system settings beyond what's needed

This follows the **principle of least privilege**—the automation user has exactly the permissions it needs, no more.

### Token Management Best Practices

1. **Never commit unencrypted tokens** to Git
2. **Use SOPS or a secrets manager** for storage
3. **Rotate tokens periodically** by setting expiration dates
4. **Revoke the root bootstrap token** after setup
5. **Audit token usage** through Proxmox logs

## Why This Matters for Your Blog

You might be wondering: "Why all this complexity for a blog?"

The answer is **scalability and security**. While we're starting with a blog, this bootstrap setup gives you:

- A secure foundation for growing your infrastructure
- The ability to add more services (databases, caches, monitoring) without credential juggling
- Clear separation between manual operations (root) and automation (tofu)
- A reproducible setup you can tear down and rebuild anytime

In the next post, we'll use this automation user to deploy our first VM cluster for hosting the blog. Stay tuned!

## Common Issues

### Authentication Failed

```
Error: 401 Unauthorized
```

Make sure your bootstrap token has root privileges and hasn't expired.

### SOPS Decryption Failed

```
Error: no key could decrypt the data
```

Ensure `age.agekey` exists in the directory and contains your private key.

### SSH Connection Failed

The provider uses SSH for certain operations. Verify:

- Your SSH key exists at `~/.ssh/keys/id_ed25519`
- The public key is in root's `authorized_keys` on the Proxmox host
- SSH access is enabled

## Next Steps

With your Proxmox environment bootstrapped, you're ready to:

1. Use the `tofu` token for all infrastructure deployments
2. Deploy VM templates for your blog
3. Set up networking and storage pools
4. Implement infrastructure monitoring

Check out the full repository for examples and documentation:
[infra/proxmox/bootstrap/users](https://github.com/yourusername/your-repo)

## Resources

- [Proxmox Terraform Provider](https://registry.terraform.io/providers/bpg/proxmox/latest/docs)
- [SOPS Documentation](https://github.com/mozilla/sops)
- [age Encryption Tool](https://github.com/FiloSottile/age)
- [OpenTofu](https://opentofu.org/)
- [Proxmox User Management](https://pve.proxmox.com/wiki/User_Management)

---

Have questions or suggestions? Let me know in the comments or open an issue on GitHub!
