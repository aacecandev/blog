---
title: "Creating Golden Images with Packer for Proxmox"
date: "2025-11-19"
description: "Learn how to build reusable VM templates with Packer and cloud-init. Part 3 of deploying your blog on Proxmox - creating the foundation for rapid VM deployment."
tags: ["proxmox", "packer", "golden-image", "cloud-init", "automation", "infrastructure"]
---

# Creating Golden Images with Packer for Proxmox

Welcome to Part 3 of our Proxmox blog deployment series! In the previous posts, we [set up our blog](./hello-world.md) and [bootstrapped Proxmox with secure automation credentials](./proxmox-bootstrap-automation.md). Now it's time to create the foundation for all our future VM deployments: a **golden image**.

## What is a Golden Image?

A golden image is a pre-configured VM template that serves as the foundation for deploying new virtual machines. Think of it as a master copy—you create it once, and then clone it whenever you need a new VM.

Instead of:

1. Manually installing Ubuntu on every new VM
2. Configuring SSH, users, and packages each time
3. Running the same updates repeatedly

You:

1. Build one perfect template
2. Clone it in seconds
3. Customize via cloud-init on first boot

This approach gives you:

- **Consistency**: Every VM starts from the same baseline
- **Speed**: Deploy VMs in seconds instead of minutes
- **Reproducibility**: Rebuild the template anytime with the same configuration
- **Version Control**: Track changes to your base images over time

## VM ID Conventions: Why 100?

Before we dive in, let me explain the VM ID numbering scheme. Proxmox assigns each VM a unique numeric ID. I use a convention to keep things organized:

- **100-199**: Reserved for golden image templates
- **200-299**: Development VMs
- **300-399**: Staging VMs
- **400-999**: Production VMs

For this golden image, we'll use **ID 100** since it's our first template. This convention makes it immediately clear what type of resource you're looking at when browsing your Proxmox interface.

## Tools of the Trade: Packer

[Packer](https://www.packer.io/) by HashiCorp is the industry standard for building automated machine images. It:

- Automates the entire VM creation process
- Supports multiple platforms (Proxmox, VMware, AWS, Azure, etc.)
- Produces consistent, reproducible builds
- Integrates with CI/CD pipelines

We'll use the **Proxmox plugin** to build our Ubuntu 24.04 LTS golden image directly on our Proxmox host.

## Understanding Proxmox Storage

Before building your golden image, you need to understand where Proxmox stores VM disks and templates. Not all storage types support VM images, and each has different performance characteristics.

### Querying Available Storage

To see what storage is available on your Proxmox node:

```bash
# Via Proxmox CLI (SSH to your Proxmox host)
pvesm status

# Example output:
# Name             Type     Status           Total            Used       Available        %
# local            dir      active       100.00 GiB       45.23 GiB       54.77 GiB   45.23%
# local-lvm        lvmthin  active       200.00 GiB       89.45 GiB      110.55 GiB   44.73%
# local-zfs        zfspool  active       500.00 GiB      123.67 GiB      376.33 GiB   24.73%
# nfs-storage      nfs      active         1.00 TiB      456.78 GiB      567.22 GiB   44.60%
```

To see which content types each storage supports:

```bash
# Detailed storage information
pvesm status --content

# Or query specific storage
pvesm status local --content

# Output shows what each storage can hold:
# local: ISO images, CT templates, Snippets, Backups
# local-lvm: VM images, CT volumes
# local-zfs: VM images, CT volumes
```

To get storage information in JSON format (useful for automation):

```bash
pvesh get /storage --output-format json-pretty

# Or for a specific storage:
pvesh get /storage/local-zfs --output-format json-pretty
```

### Storage Types and VM Image Support

Here's a breakdown of common Proxmox storage types and their capabilities:

#### 1. **Directory (dir)** - Local filesystem storage

```bash
# Typically: /var/lib/vz or custom mount points
pvesm status | grep dir
```

**Characteristics:**

- **Supports**: ISO images, container templates, backups, snippets
- **Does NOT support**: VM disk images by default
- **Format**: Raw files on filesystem
- **Performance**: Depends on underlying filesystem (ext4, xfs)
- **Use case**: ISO storage, backups, configuration files

**Example:** `local` storage

- Path: `/var/lib/vz`
- Content types: `vztmpl,iso,backup,snippets`

**Why not for VM images?** Directory storage can technically store VM images as files, but Proxmox doesn't enable this by default because it lacks thin provisioning and snapshot capabilities that LVM-thin or ZFS provide.

#### 2. **LVM-Thin (lvmthin)** - Logical Volume Manager with thin provisioning

```bash
pvesm status | grep lvmthin
```

**Characteristics:**

- **Supports**: VM disk images, container volumes
- **Format**: Logical volumes with thin provisioning
- **Performance**: Very good (block-level storage)
- **Snapshots**: Yes (efficient, COW snapshots)
- **Thin provisioning**: Yes (only use space that's written)
- **Use case**: Primary VM disk storage

**Example:** `local-lvm` storage

- Based on: Volume group `pve`
- Thin pool: `data`
- Content types: `images,rootdir`

**Benefits:**

- Over-provisioning possible (allocate 1TB, but only use space that's written)
- Fast snapshots for backups
- Good performance for most workloads

**Limitations:**

- Cannot store ISO files or snippets
- Less flexible than filesystem storage
- Requires LVM expertise for management

#### 3. **ZFS (zfspool)** - Zettabyte File System

```bash
pvesm status | grep zfspool
```

**Characteristics:**

- **Supports**: VM disk images, container volumes
- **Format**: ZFS zvols (block devices)
- **Performance**: Excellent (especially for random I/O)
- **Snapshots**: Yes (instant, efficient)
- **Compression**: Optional (lz4, zstd)
- **Deduplication**: Optional (but RAM-intensive)
- **Data integrity**: Built-in checksums and self-healing
- **Use case**: Production VM storage, databases

**Example:** `local-zfs` storage

- Pool: `rpool` or custom pool
- Content types: `images,rootdir`

**Benefits:**

- Best data integrity (checksums on everything)
- Instant snapshots with minimal overhead
- Optional compression (saves disk space)
- Highly configurable (recordsize, compression, etc.)
- Excellent performance with proper tuning

**Limitations:**

- Requires more RAM (1GB per TB is the recommendation)
- Cannot store ISO files or snippets
- More complex to set up and tune

#### 4. **NFS (nfs)** - Network File System

```bash
pvesm status | grep nfs
```

**Characteristics:**

- **Supports**: VM disk images, ISO images, backups, snippets, templates
- **Format**: Files on remote NFS server
- **Performance**: Network-dependent, generally slower than local
- **Snapshots**: Depends on NFS server capabilities
- **Use case**: Shared storage across multiple Proxmox nodes, centralized ISO library

**Example:** `nfs-storage`

- Server: `nas.example.com:/volume1/proxmox`
- Content types: `images,iso,vztmpl,backup,snippets`

**Benefits:**

- Shared across multiple Proxmox nodes (for HA clustering)
- Can store all content types
- Easy to expand (just add space on NFS server)
- Centralized management

**Limitations:**

- Network performance bottleneck
- Latency can affect VM performance
- Single point of failure (unless NFS server is HA)

#### 5. **Ceph (rbd)** - Distributed storage

```bash
pvesm status | grep rbd
```

**Characteristics:**

- **Supports**: VM disk images, container volumes
- **Format**: RADOS Block Device
- **Performance**: Scales horizontally
- **Replication**: Built-in (3x default)
- **Use case**: Large clusters, high availability

**Benefits:**

- Distributed and redundant
- No single point of failure
- Scales with cluster size
- Live migration support

**Limitations:**

- Complex to set up
- Requires at least 3 nodes
- Higher resource overhead

### Storage Configuration in Packer

In your Packer configuration, you'll specify which storage to use:

```hcl
source "proxmox-iso" "ubuntu" {
  # Disk storage - where the VM disk is created
  disks {
    disk_size    = "20G"
    storage_pool = "local-zfs"    # ← Must support VM images!
    type         = "scsi"
    format       = "raw"           # or "qcow2"
  }

  # ISO storage - where the ISO is stored
  iso_file         = "local:iso/ubuntu-24.04.3-live-server-amd64.iso"
  iso_storage_pool = "local"       # ← Can be directory storage

  # Cloud-init storage - where cloud-init disk is created
  cloud_init              = true
  cloud_init_storage_pool = "local-zfs"  # ← Must support VM images!
}
```

### How to Choose Storage for Your Golden Image

**For the template disk (`storage_pool`):**

| Storage Type | Recommendation | Why |
|-------------|----------------|-----|
| **ZFS** | ⭐ Best choice | Fast cloning, compression, integrity checking |
| **LVM-Thin** | ⭐ Good choice | Fast cloning, thin provisioning, widely supported |
| **Local Dir** | ❌ Not supported | Cannot store VM images by default |
| **NFS** | ⚠️ Works but slower | Network overhead, use only if sharing across nodes |
| **Ceph** | ⭐ Best for clusters | Distributed, redundant, but overkill for single node |

**For ISO storage (`iso_storage_pool`):**

| Storage Type | Recommendation | Why |
|-------------|----------------|-----|
| **Local Dir** | ⭐ Best choice | Simple, no overhead, perfect for read-only files |
| **NFS** | ⭐ Good for clusters | Share ISOs across all nodes |
| **ZFS/LVM** | ❌ Not supported | These don't support ISO content type |

### Real-World Example

Here's my Proxmox setup:

```bash
$ pvesm status
Name          Type     Status  Total       Used     Available  %
local         dir      active  100.00 GiB  48.21 GiB  51.79 GiB  48.21%
local-lvm     lvmthin  active  200.00 GiB  78.45 GiB 121.55 GiB  39.23%
local-zfs     zfspool  active  500.00 GiB 145.67 GiB 354.33 GiB  29.13%
```

**How I use each storage:**

- **`local`**: ISO images, backups, cloud-init snippets
- **`local-lvm`**: Not used (I prefer ZFS)
- **`local-zfs`**: All VM disks and templates (my golden image lives here)

**Why ZFS?**

- Instant template cloning (< 1 second)
- Compression saves ~30% disk space
- Checksums ensure data integrity
- Fast snapshots for backups

**My Packer configuration** in `variables.auto.pkrvars.hcl`:

```hcl
proxmox_iso_pool     = "local"       # ISO stored here
proxmox_storage_pool = "local-zfs"   # Template disk & cloud-init here
```

### Verifying Your Storage Setup

Before building, verify your storage can handle VM images:

```bash
# Check if your target storage supports VM images
pvesm status local-zfs --content

# Should show: images,rootdir in the content types

# Check available space
pvesm status local-zfs

# Make sure you have at least 20GB free for the template
```

If your desired storage doesn't support VM images:

```bash
# You can modify storage content types (⚠️ be careful!)
# Edit: /etc/pve/storage.cfg

# Example - enable images on directory storage (not recommended)
dir: local
    path /var/lib/vz
    content vztmpl,iso,backup,snippets,images  # Added 'images'

# Apply changes (automatically reloaded)
```

**Warning**: Enabling VM images on directory storage removes thin provisioning and snapshot benefits. Only do this for testing or if you have a specific reason.

## Repository Structure

Here's what our golden image repository contains:

```
infra/proxmox/bootstrap/golden-image/
├── packer.pkr.hcl                      # Main Packer configuration (source & build)
├── variables.pkr.hcl                   # Variable declarations only
├── variables.auto.pkrvars.hcl          # Non-sensitive configuration values
├── variables.auto.pkrvars.hcl.example  # Configuration template
├── secrets.auto.pkrvars.hcl            # Encrypted secrets (SOPS)
├── secrets.auto.pkrvars.hcl.example    # Secrets template
├── .sops.yaml                          # SOPS configuration
├── age.agekey                          # Age encryption key (gitignored)
├── .gitignore                          # Git ignore rules
├── README.md                           # Documentation
└── http/                               # Cloud-init configuration
    ├── user-data                       # Autoinstall config
    └── meta-data                       # Metadata
```

The repository follows a clean separation of concerns:

- **packer.pkr.hcl**: Contains only the packer plugin configuration, source block, and build block—no variables or hardcoded values
- **variables.pkr.hcl**: All variable declarations with types, descriptions, and default values for non-sensitive options
- **variables.auto.pkrvars.hcl**: Infrastructure settings that are safe to commit (node names, storage pools, template configuration)
- **secrets.auto.pkrvars.hcl**: Sensitive values encrypted with SOPS (API credentials, SSH passwords, IP addresses)

## Using the Bootstrap Token

Remember the automation token we created in Part 2? Now we'll use it! The golden image build needs API access to Proxmox to create and configure the template VM.

### Step 1: Retrieve the Token

Navigate to your bootstrap users directory and decrypt the secrets:

```bash
cd /path/to/infra/proxmox/bootstrap/users

# Decrypt the terraform.tfvars file temporarily
sops -d -i terraform.tfvars

# Get the token value
tofu output -raw tofu__api_token

# Re-encrypt the file
sops -e -i terraform.tfvars
```

This outputs your token in the format:

```
tofu@pve!deployment=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Copy this token—we'll need it in the next step.

### Step 2: Configure Golden Image Secrets

Now navigate to the golden image directory and set up encryption:

```bash
cd /path/to/infra/proxmox/bootstrap/golden-image

# Generate an age key for this repository
age-keygen -o age.agekey

# Copy the example files
cp variables.auto.pkrvars.hcl.example variables.auto.pkrvars.hcl
cp secrets.auto.pkrvars.hcl.example secrets.auto.pkrvars.hcl

# Edit non-sensitive configuration
nano variables.auto.pkrvars.hcl
```

Configure your infrastructure settings in `variables.auto.pkrvars.hcl`:

```hcl
# Non-sensitive configuration values
proxmox_node              = "pve-1"
proxmox_iso_pool          = "local"
proxmox_storage_pool      = "local-zfs"
proxmox_storage_format    = "raw"
template_name             = "Ubuntu-24.04-Template"
template_description      = "Ubuntu 24.04 Template"
ubuntu_image              = "ubuntu-24.04.3-live-server-amd64.iso"
vm_id                     = 100
```

Now edit `secrets.auto.pkrvars.hcl` with your sensitive values:

```bash
nano secrets.auto.pkrvars.hcl
```

Add your Proxmox credentials and SSH configuration:

```hcl
# Proxmox API Credentials
proxmox_url      = "https://192.168.1.200:8006/api2/json"
proxmox_username = "tofu@pve!deployment"
proxmox_token    = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

# SSH Credentials
ssh_username = "ubuntu"
ssh_password = "ubuntu"
ssh_host     = "192.168.1.100"
```

Encrypt only the secrets file with SOPS:

```bash
# Update .sops.yaml with your age public key
# (found at the top of age.agekey)

# Encrypt the secrets file
sops -e -i secrets.auto.pkrvars.hcl
```

**Why SOPS again?** You might be wondering why we're using SOPS + age for yet another repository. The answer is simple: we don't have a centralized secrets management solution yet. Each repository needs its secrets encrypted at rest, so we use SOPS until we implement something like HashiCorp Vault or AWS Secrets Manager. It's not ideal to have multiple age keys, but it's secure and functional for now.

**Note**: The `variables.auto.pkrvars.hcl` file remains unencrypted since it contains only non-sensitive configuration that's safe to commit to version control.

## The Build Process

### What Gets Created

The Packer template creates an Ubuntu 24.04 LTS VM with:

- **QEMU Guest Agent**: For better VM management and monitoring
- **Cloud-init**: For automated configuration on first boot
- **SSH Server**: Pre-configured and ready
- **Clean State**: No machine-id, SSH host keys, or logs (generated on first boot)
- **Minimal Footprint**: Unnecessary packages removed

### Using the Downloaded ISO

In `packer.pkr.hcl`, the boot_iso configuration references the ISO we downloaded earlier:

```hcl
boot_iso {
  iso_file         = "${var.proxmox_iso_pool}:iso/${var.ubuntu_image}"
  iso_storage_pool = var.proxmox_iso_pool
  unmount          = true
}
```

With your `variables.auto.pkrvars.hcl` settings:

```hcl
proxmox_iso_pool = "local"
ubuntu_image     = "ubuntu-24.04.3-live-server-amd64.iso"
```

This references the **exact same ISO** we downloaded in the bootstrap users repository! We're not downloading it again—Packer uses the ISO already stored in your Proxmox `local` datastore. This saves time and bandwidth on every build.

### The Autoinstall Process

Packer uses Ubuntu's **autoinstall** feature (a declarative replacement for the old preseed method) to automatically install the OS. Here's what happens:

1. **Packer creates a temporary VM** (ID 100) on your Proxmox host
2. **Boots from the Ubuntu ISO** we downloaded earlier
3. **Serves the autoinstall config** via HTTP from your workstation
4. **Ubuntu installer reads** `http/user-data` and performs an unattended installation
5. **Packer provisions** the VM (installs packages, cleans up, configures cloud-init)
6. **Converts to template** and shuts down

The entire process takes about 5-10 minutes.

### Cloud-Init Configuration

The `http/user-data` file defines what gets installed:

```yaml
#cloud-config
autoinstall:
  version: 1
  locale: en_US
  keyboard:
    layout: es
  network:
    version: 2
    ethernets:
      ens18:
        dhcp4: true
  packages:
    - qemu-guest-agent
    - sudo
  user-data:
    package_upgrade: false
    timezone: Europe/Madrid
    users:
      - name: ubuntu
        passwd: $6$xyz$lrzkz89JCrvzOPr...
        groups: [adm, sudo]
        sudo: ALL=(ALL) NOPASSWD:ALL
```

This creates a base `ubuntu` user with password authentication (for initial access during the build). When you deploy VMs from this template, you'll inject your own SSH keys and configuration via cloud-init.

## Building the Golden Image

### Step 1: Initialize Packer

```bash
# Source environment variables
source .envrc

# Or if using direnv
direnv allow

# Initialize Packer plugins
packer init .
```

### Step 2: Validate Configuration

```bash
packer validate .
```

This checks:

- HCL syntax is correct
- Variables are properly defined
- Required plugins are available
- Credentials can decrypt (via SOPS)

### Step 3: Verify `ssh_host` Configuration (CRITICAL!)

**Before building**, verify your `ssh_host` is configured correctly. This is the #1 cause of build failures!

```bash
# 1. Check what ssh_host is configured in your secrets file
sops -d secrets.auto.pkrvars.hcl | grep ssh_host

# 2. Verify the IP is available
ping -c 3 192.168.1.100  # Replace with your ssh_host

# 3. Ensure you can reach Proxmox
ping -c 3 192.168.1.200  # Your Proxmox IP

# 4. Test SSH to Proxmox (should work with your key)
ssh root@192.168.1.200 "echo Connection successful"
```

If any of these fail, **stop** and fix the issues before building. See the [Critical Configuration: The ssh_host Variable](#critical-configuration-the-ssh_host-variable) section for detailed guidance.

### Step 4: Build

```bash
# Using Packer directly
packer build .

# Or using the Makefile
make build
```

Watch the output as Packer:

1. Creates VM 100 on your Proxmox node
2. Boots the Ubuntu installer
3. Serves autoinstall configuration
4. Waits for installation to complete
5. **Connects via SSH to `ssh_host`** ← This is where most builds fail!
6. Runs provisioning scripts
7. Cleans and prepares the template
8. Converts the VM to a template

### Step 5: Verify

Once complete, check your Proxmox interface:

```bash
# Via CLI
qm list | grep 100

# Output:
# 100  ubuntu2404-golden-image   0     2048  20G    stopped
```

You should see VM 100 as a **template** (indicated by a special icon in the web UI).

## What Happens During Provisioning

The Packer provisioner runs several important cleanup steps:

```bash
# Remove SSH host keys (regenerated on first boot)
sudo rm -f /etc/ssh/ssh_host_*

# Clear machine-id (ensures unique VMs)
sudo truncate -s 0 /etc/machine-id

# Install QEMU Guest Agent
sudo apt-get install -y qemu-guest-agent
sudo systemctl enable qemu-guest-agent

# Clean logs and temporary files
sudo find /var/log -type f -exec truncate -s 0 {} \;
sudo rm -rf /tmp/* /var/tmp/*

# Clean cloud-init state
sudo cloud-init clean --logs --seed
```

This ensures every VM cloned from the template gets:

- Unique SSH host keys
- Unique machine-id
- Clean logs
- Fresh cloud-init configuration

### The Secret Sauce: 99-pve.cfg

One critical file gets copied during provisioning:

```yaml
# files/99-pve.cfg
datasource_list: [ConfigDrive, NoCloud]
```

This tells cloud-init to **only** check Proxmox-compatible datasources. Without this, cloud-init wastes ~2 minutes on every boot checking for AWS, Azure, and other cloud platforms. This simple config file shaves 2 minutes off your VM boot times!

## Critical Configuration: The `ssh_host` Variable

Before you build your golden image, there's **one configuration that can make or break your build**: the `ssh_host` variable. This is the most common source of build failures, and understanding it is crucial for success.

### What is `ssh_host`?

In your `packer.pkr.hcl` configuration, the SSH settings reference variables:

```hcl
source "proxmox-iso" "autogenerated_1" {
  # ... other configuration ...

  ssh_username = var.ssh_username
  ssh_password = var.ssh_password
  ssh_host     = var.ssh_host     # ← THIS IS CRITICAL!
  ssh_port     = var.ssh_port
  ssh_timeout  = var.ssh_timeout
}
```

These values come from your `secrets.auto.pkrvars.hcl` file:

```hcl
ssh_username = "ubuntu"
ssh_password = "ubuntu"
ssh_host     = "192.168.1.100"  # ← THIS IS CRITICAL!
```

The `ssh_host` tells Packer **which IP address to use when connecting to the temporary VM during the build process**. Packer needs to SSH into the VM to run provisioning scripts, and if it can't connect, the entire build fails.

### Why It's Critical: The Build Flow

Here's what happens during a Packer build:

```
1. Packer creates a temporary VM on Proxmox (ID 100)
2. VM boots from Ubuntu ISO
3. Autoinstall runs, configures OS
4. VM gets an IP address (from DHCP or static config)
5. ⚠️  Packer tries to SSH to ssh_host IP  ⚠️
6. If successful: provisioning scripts run
7. If failed: build times out after 30 minutes
```

**The Problem**: If the VM gets a different IP than what's configured in `ssh_host`, or if Packer can't reach that IP, the build hangs at step 5 and eventually fails with:

```
Error waiting for SSH to become available: timeout
```

### How to Configure `ssh_host` Correctly

The `ssh_host` IP must meet these requirements:

1. **Reachable from your workstation** (where Packer runs)
2. **On the same network as Proxmox** (usually the same subnet)
3. **Available** (not currently used by another device)
4. **Assigned to the VM during boot** (via DHCP or configured in autoinstall)

#### Network Diagram

```
┌─────────────────────┐                  ┌───────────────────────┐
│  Your Workstation   │                  │   Proxmox Host        │
│  (Running Packer)   │                  │   192.168.1.200       │
│                     │                  │                       │
│  $ packer build .   │  SSH to          │  ┌─────────────────┐  │
│                     │  192.168.1.100   │  │ Temp VM (ID100) │  │
│                     ├─────────────────→│  │                 │  │
│                     │  Must Reach!     │  │ IP: ssh_host    │  │
│                     │                  │  │ 192.168.1.100   │  │
│                     │                  │  │                 │  │
│                     │                  │  │ Provisioning... │  │
│                     │                  │  └─────────────────┘  │
│                     │                  │         ↓             │
│                     │                  │  ┌─────────────────┐  │
│                     │                  │  │ Template Ready  │  │
│                     │                  │  └─────────────────┘  │
└─────────────────────┘                  └───────────────────────┘
         │                                          │
         └────── Same Network (192.168.1.0/24) ────┘
```

#### Configuration Options

**Option 1: Use a Reserved DHCP IP (Recommended)**

The simplest approach is to pick an available IP in your network's DHCP range and ensure it's not currently in use:

```bash
# Test if IP is available
ping -c 3 192.168.1.100

# If no response, it's free!
```

Set this in your `secrets.auto.pkrvars.hcl`:

```hcl
ssh_host = "192.168.1.100"  # Change to match your network
```

Your `http/user-data` should configure the VM to use DHCP:

```yaml
network:
  version: 2
  ethernets:
    ens18:
      dhcp4: true  # VM will get an IP from DHCP
```

**Option 2: Configure Static IP in Autoinstall**

For more control, set a static IP in your autoinstall configuration that matches `ssh_host`:

```yaml
# http/user-data
network:
  version: 2
  ethernets:
    ens18:
      addresses:
        - 192.168.1.100/24  # Must match ssh_host!
      gateway4: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 1.1.1.1]
```

**Option 3: DHCP Reservation**

Configure your DHCP server (router or Proxmox) to always assign the same IP to the VM:

```bash
# Example: On a router with dnsmasq
# /etc/dnsmasq.conf
dhcp-host=52:54:00:12:34:56,192.168.1.100,packer-build

# Restart dnsmasq
sudo systemctl restart dnsmasq
```

### Real-World Example

In my setup:

- **Proxmox host**: `192.168.1.200` (management interface)
- **Network**: `192.168.1.0/24`
- **DHCP range**: `192.168.1.100-192.168.1.199`
- **ssh_host**: `192.168.1.100` (first IP in DHCP range)

This works because:

1. My workstation is on the same `192.168.1.0/24` network
2. The IP `192.168.1.100` is in my DHCP range
3. I verified it wasn't in use before building
4. The temporary VM gets this IP from DHCP during boot
5. Packer successfully connects and provisions

### Pre-Build Checklist

Before running `packer build`, verify:

- [ ] `ssh_host` IP is in your network's subnet
- [ ] IP is not currently in use: `ping -c 3 <ssh_host_ip>`
- [ ] You can reach your Proxmox host: `ping -c 3 192.168.1.200`
- [ ] SSH connectivity works: `ssh root@192.168.1.200` (should work with your key)
- [ ] Firewall allows SSH (port 22) between your workstation and Proxmox network
- [ ] Network bridge in Packer config matches Proxmox: `bridge = "vmbr0"`

### Common Scenarios and Solutions

#### Scenario 1: Different Network Segments

If your workstation is on a different network than Proxmox:

```
Workstation: 10.0.0.0/24
Proxmox:     192.168.1.0/24
```

**Solution**: Either:

- Run Packer directly on the Proxmox host
- Set up routing between networks
- Use a VPN to join both networks

#### Scenario 2: VM Gets Wrong IP

Build fails because VM got `192.168.1.150` but `ssh_host` is `192.168.1.100`.

**Solution**:

- Use static IP in `http/user-data` (Option 2 above)
- Or configure DHCP reservation (Option 3 above)

#### Scenario 3: Firewall Blocking SSH

Build times out waiting for SSH, but VM has correct IP.

**Solution**:

```bash
# On Proxmox host, check firewall rules
iptables -L -n -v | grep 22

# Temporarily disable Proxmox firewall for testing
systemctl stop pve-firewall

# Try build again
packer build .

# Re-enable firewall
systemctl start pve-firewall
```

### Advanced: Dynamic IP Discovery

Some Packer builders support dynamic IP discovery, but the Proxmox ISO builder requires explicit `ssh_host`. A workaround is using Proxmox's QEMU guest agent, but that requires the agent to be installed before Packer can connect—a chicken-and-egg problem during initial builds.

For now, stick with explicit `ssh_host` configuration. It's predictable and reliable.

## Using the Golden Image

Now that you have a template, deploying VMs is trivial:

### Option 1: Proxmox Web UI

1. Right-click template 100
2. Select "Clone"
3. Choose "Full Clone"
4. Set VM ID (e.g., 201 for a dev server)
5. Configure cloud-init (SSH keys, IP, etc.)
6. Start the VM

### Option 2: Terraform/OpenTofu

```hcl
resource "proxmox_virtual_environment_vm" "blog_server" {
  node_name = "pve-1"
  vm_id     = 201
  name      = "blog-server-dev"

  clone {
    vm_id = 100  # Our golden image!
  }

  initialization {
    user_account {
      username = "admin"
      keys     = ["ssh-ed25519 AAAAC3Nza..."]
    }

    ip_config {
      ipv4 {
        address = "dhcp"
      }
    }
  }
}
```

The VM boots in seconds, already configured with your SSH keys and network settings.

## Makefile Shortcuts

The repository includes a Makefile for common tasks:

```bash
# Show available commands
make help

# Initial setup (copy examples, init, install hooks)
make setup

# Validate configuration
make validate

# Format HCL files
make fmt

# Build the image
make build

# Clean up artifacts
make clean
```

## Updating the Golden Image

Golden images aren't static—you'll want to update them periodically for security patches and new features.

### When to Rebuild

- **Monthly**: For OS security updates
- **As Needed**: When you need new base packages
- **Major Releases**: When Ubuntu releases a new LTS version

### How to Update

```bash
# Make changes to http/user-data or packer.pkr.hcl
vim http/user-data

# Rebuild
make build

# Optional: Create a new version (e.g., ID 101) instead of overwriting
# Edit variables.auto.pkrvars.hcl and change vm_id to 101
```

### Version Control

Tag your golden image builds:

```bash
git tag -a v1.0.0 -m "Ubuntu 24.04.3 LTS base image"
git push --tags
```

This lets you track what was included in each template version.

## Security Considerations

### Secrets Management (Again!)

Yes, we're using SOPS + age again. Each repository has its own age key because:

1. **Isolation**: Compromise of one key doesn't affect other repos
2. **Access Control**: Different people may need access to different repos
3. **Temporary Solution**: We'll centralize secrets management in a future post

For now, treat each `age.agekey` file as highly sensitive:

```bash
# Make sure it's in .gitignore
echo "age.agekey" >> .gitignore

# Set proper permissions
chmod 600 age.agekey

# Back it up securely (encrypted drive, password manager, etc.)
```

### Template Security

The template includes a default `ubuntu` user with a known password (`ubuntu`). This is acceptable because:

1. **It's only used during the build** (Packer needs to SSH in)
2. **Cloud-init replaces it** with your configured users on deployment
3. **The password hash is public** (in user-data) but the template is never exposed to networks

For production templates, consider:

- Using SSH keys only (no password)
- Removing the default user entirely
- Implementing more restrictive sudo rules

## CI/CD Integration

The repository includes GitHub Actions workflows for automated building:

```yaml
# .github/workflows/build.yml
name: Build Golden Image
on:
  workflow_dispatch:
  push:
    tags: ['v*']
  schedule:
    - cron: '0 0 1 * *'  # Monthly rebuild
```

This automatically rebuilds your golden image:

- When you push a version tag
- On the first of every month (for security updates)
- Manually via GitHub Actions UI

**Note**: This requires either:

- A self-hosted GitHub Actions runner (recommended)
- VPN/Tailscale access from GitHub to your Proxmox host
- Securely exposed Proxmox API endpoint

## What's Next?

With our golden image ready, we have everything we need to rapidly deploy VMs:

- ✅ Secure automation credentials (`tofu@pve` user)
- ✅ Pre-downloaded Ubuntu ISO
- ✅ Golden image template (ID 100)

In the next post, we'll use this template to deploy our first application cluster: a highly-available K3s Kubernetes setup for hosting our blog and other services.

## Troubleshooting

### Build Fails at SSH Connection

This is the **most common failure** when building golden images. The build hangs for 30 minutes then fails with:

```
==> proxmox-iso.ubuntu: Waiting for SSH to become available...
==> proxmox-iso.ubuntu: Error waiting for SSH: ssh: connect to host 192.168.1.100 port 22: Connection timed out
Build 'proxmox-iso.ubuntu' errored after 30 minutes: Timeout waiting for SSH.
```

#### Step 1: Verify VM Got the Correct IP

First, check if the VM is running and what IP it actually has:

```bash
# Via Proxmox CLI
qm list | grep 100

# If VM exists, check its console in Proxmox web UI
# Navigate to: VM 100 > Console

# In the VM console, login with ubuntu/ubuntu and check IP:
ip addr show
```

**If the VM has a different IP than `ssh_host`**:

- Update `ssh_host` in your Packer config to match
- OR configure static IP in `http/user-data` (see [ssh_host section](#critical-configuration-the-ssh_host-variable))

**If the VM has no IP or shows "FAILED" network status**:

- Check your `http/user-data` network configuration
- Verify network bridge exists: `brctl show` on Proxmox host
- Confirm DHCP server is running and accessible

#### Step 2: Test Network Connectivity

From your workstation where Packer runs:

```bash
# Can you ping the VM?
ping -c 3 192.168.1.100

# Can you reach SSH port?
nc -zv 192.168.1.100 22

# Or using nmap
nmap -p 22 192.168.1.100
```

**If ping fails**:

- Check routing: `traceroute 192.168.1.100`
- Verify you're on the same network as Proxmox
- Check if VPN or firewall is blocking traffic

**If SSH port is closed**:

- SSH server may not be installed yet (autoinstall in progress)
- Wait a few more minutes for installation to complete
- Check VM console for installation errors

#### Step 3: Verify SSH from Proxmox Host

If your workstation can't reach the VM, try from the Proxmox host itself:

```bash
# SSH to Proxmox
ssh root@192.168.1.200

# From Proxmox, try to SSH to the building VM
ssh ubuntu@192.168.1.100
# Password: ubuntu
```

**If this works but your workstation can't connect**:

- Network routing issue between your workstation and Proxmox
- Consider running Packer directly on Proxmox host
- Or set up proper routing/VPN

**If this fails from Proxmox too**:

- VM network configuration is wrong
- Firewall on Proxmox is blocking traffic
- VM is on wrong bridge/VLAN

#### Step 4: Check Common Misconfigurations

**Wrong bridge in Packer config:**

```hcl
# In your packer.pkr.hcl
network_adapters {
  model    = "virtio"
  bridge   = "vmbr0"    # ← Verify this exists on your Proxmox
  firewall = false
}
```

Verify bridges on Proxmox:

```bash
brctl show
```

**Firewall blocking connections:**

```bash
# Check Proxmox firewall status
pve-firewall status

# Temporarily disable for testing (NOT for production!)
systemctl stop pve-firewall

# Try build again
packer build .

# Re-enable
systemctl start pve-firewall
```

**ssh_host not matching autoinstall network config:**

Your `http/user-data` should either:

1. Use DHCP (simplest):

   ```yaml
   network:
     version: 2
     ethernets:
       ens18:
         dhcp4: true
   ```

2. OR use static IP matching `ssh_host`:

   ```yaml
   network:
     version: 2
     ethernets:
       ens18:
         addresses: [192.168.1.100/24]  # Must match ssh_host!
         gateway4: 192.168.1.1
         nameservers:
           addresses: [8.8.8.8]
   ```

#### Step 5: Watch the Build in Real-Time

Open two terminals:

**Terminal 1: Run Packer with debug logging**

```bash
export PACKER_LOG=1
export PACKER_LOG_PATH=packer-build.log
packer build .
```

**Terminal 2: Monitor Proxmox events**

```bash
ssh root@192.168.1.200
tail -f /var/log/pve/tasks/active
```

This helps you see exactly when and where the build fails.

### SOPS Decryption Error

```
Error: no key could decrypt the data
```

**Solution**: Ensure `SOPS_AGE_KEY_FILE` is set:

```bash
export SOPS_AGE_KEY_FILE=./age.agekey
source .envrc
```

### ISO Not Found

```
Error: ISO not found: local:iso/ubuntu-24.04.3-live-server-amd64.iso
```

**Solution**: Go back to Part 2 and ensure the bootstrap users repository downloaded the ISO successfully:

```bash
cd infra/proxmox/bootstrap/users
tofu apply  # Re-run if needed
```

### Template Already Exists

```
Error: VM 100 already exists
```

**Solution**: Delete the existing template first:

```bash
qm destroy 100
```

Or change `vm_id` in `variables.auto.pkrvars.hcl` to use a different ID (e.g., 101).

## Resources

- [Packer Documentation](https://www.packer.io/docs)
- [Packer Proxmox Plugin](https://www.packer.io/plugins/builders/proxmox/iso)
- [Ubuntu Autoinstall](https://ubuntu.com/server/docs/install/autoinstall)
- [Cloud-init Documentation](https://cloudinit.readthedocs.io/)
- [Proxmox Cloud-Init Support](https://pve.proxmox.com/wiki/Cloud-Init_Support)

---

Building golden images might seem like extra work upfront, but it's one of those infrastructure investments that pays dividends. Instead of waiting 15 minutes for a manual install, you'll deploy production-ready VMs in under 60 seconds.

In the next post, we'll put this golden image to work by deploying a K3s cluster for our blog. Stay tuned!

Have questions about golden images or Packer? Drop a comment below!
