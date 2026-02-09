---
title: "Securing Your Homelab Network with OPNsense on Proxmox"
date: "2025-12-01"
description: "Set up OPNsense as a virtual router and firewall inside Proxmox with NIC passthrough, network segmentation, and WireGuard VPN for remote access. Part 5 of our Proxmox infrastructure series."
tags: ["proxmox", "opnsense", "networking", "firewall", "wireguard", "vpn", "homelab", "security"]
---

# Securing Your Homelab Network with OPNsense on Proxmox

Welcome to Part 5 of our Proxmox infrastructure series! We've [bootstrapped Proxmox](./proxmox-bootstrap-automation.md), [created golden images with Packer](./creating-golden-images-with-packer.md), and [deployed a Vault cluster](./deploying-hashicorp-vault-on-proxmox.md). Now it's time to tackle something that underpins everything else: the network.

In this post, we'll turn our Proxmox node into a proper network gateway by running OPNsense as a VM. By the end, you'll have a segmented network with a real firewall, DNS, DHCP, and WireGuard VPN for remote access.

## Why Bother With Network Segmentation?

If you're running everything on a flat network behind your ISP router, every device can talk to every other device. Your Proxmox VMs, your phone, your laptop, and whatever your ISP router exposes to the internet are all one lateral movement away from each other.

For a homelab that's running Vault, VMs, and potentially sensitive workloads, this is worth fixing:

- **Isolation**: A compromised IoT device or guest laptop can't reach your Proxmox management interface
- **Visibility**: A proper firewall gives you logs and control over what talks to what
- **DNS control**: Block ads, resolve internal hostnames, and stop DNS leaks
- **Remote access**: WireGuard on your own firewall is more trustworthy than poking holes in your ISP router
- **Learning**: Running your own network stack is one of the most valuable homelab skills

## Architecture Overview

Here's what we're building:

```
Internet
   |
+--+----------+
|  ISP Router  |  Bridge mode or DMZ to OPNsense
|              |
+--+-----------+
   |
   | NIC1 (PCIe passthrough to OPNsense VM)
   |
+--+---------------------------------------------+
|  Proxmox Node                                   |
|                                                  |
|  +------------------+                            |
|  | OPNsense VM      |                            |
|  |                  |                            |
|  | vtnet0: WAN  <---+--- NIC1 (passthrough)      |
|  | vtnet1: LAN  ----+--- vmbr1 (internal bridge) |
|  +------------------+                            |
|          |                                       |
|       vmbr1 (10.0.0.0/24)                       |
|     +----+----+--------+                        |
|     |         |        |                        |
|  +--+--+  +--+--+  +--+--+                     |
|  | VM  |  | VM  |  | CT  |                     |
|  +-----+  +-----+  +-----+                     |
|                                                  |
|  NIC2: Proxmox management (vmbr0, 192.168.1.x)  |
|  WiFi: disabled                                  |
+-------------------------------------------------+
```

The key ideas:

- **NIC1** is passed through directly to the OPNsense VM. It becomes the WAN interface. Proxmox doesn't touch this NIC at all.
- **vmbr1** is a virtual bridge with no physical port. It's the internal LAN. OPNsense is the gateway, and all VMs/CTs connect here.
- **NIC2** stays on `vmbr0` connected to your ISP router's subnet. This is your fallback management path to the Proxmox UI. If OPNsense goes down, you can still reach Proxmox.
- **WiFi NIC** is disabled. You can repurpose it later as an access point if you want.

## VM vs Dedicated Device: Why We Chose the VM Approach

I considered running OPNsense on a Raspberry Pi, but for a single-node homelab, the VM approach wins:

| Factor | Proxmox VM | Raspberry Pi |
|--------|-----------|--------------|
| Extra hardware needed | None | Pi + USB ethernet adapter |
| Performance | Full x86 CPU, fast crypto | ARM, limited throughput |
| WireGuard speed | Line rate | ~300 Mbps max |
| Management | Single interface (Proxmox) | Separate device to maintain |
| NIC passthrough | Already doing GPU passthrough | N/A |
| Cost | $0 | $50-80 |

### The Chicken-and-Egg Problem

There's one real downside: if Proxmox reboots, your network goes down. OPNsense is a VM, so no Proxmox means no router.

For a single-person homelab, this is acceptable. Here's how we mitigate it:

- **Auto-start**: OPNsense VM starts automatically on boot with the highest priority (boot order 1)
- **Management fallback**: NIC2 on `vmbr0` connects directly to the ISP router. You can always reach the Proxmox UI at `192.168.1.x` even when OPNsense is down.
- **Fast recovery**: Proxmox boots in under a minute. OPNsense is up within 30 seconds after that.

If you later add a second Proxmox node or need 24/7 uptime, you can migrate to a dedicated device. For now, this is the pragmatic choice.

## Prerequisites

Before we start, gather this information:

### Hardware Inventory

SSH into your Proxmox node and identify your NICs:

```bash
# List all network interfaces
ip link show

# Example output:
# 1: lo: ...
# 2: enp6s0: ...    <-- NIC1 (will be WAN, passthrough to OPNsense)
# 3: enp7s0: ...    <-- NIC2 (Proxmox management, stays on vmbr0)
# 4: wlp5s0: ...    <-- WiFi (disabled)
```

Note the PCI addresses:

```bash
# Find PCI addresses for your NICs
lspci | grep -i ethernet

# Example output:
# 06:00.0 Ethernet controller: Realtek RTL8111/8168/8411
# 07:00.0 Ethernet controller: Intel I211 Gigabit
```

The NIC you want to passthrough (NIC1) needs its PCI address. In this example, `06:00.0`.

### Confirm IOMMU Support

Since you're already doing GPU passthrough, IOMMU should be enabled. Verify:

```bash
dmesg | grep -i iommu

# You should see something like:
# DMAR: IOMMU enabled
# or
# AMD-Vi: IOMMU performance counters supported
```

### Check the IOMMU Group

The NIC must be in its own IOMMU group (or share it only with devices you don't need):

```bash
# Find the IOMMU group for your NIC
find /sys/kernel/iommu_groups/ -type l | sort -V | while read f; do
  echo "Group $(basename $(dirname $f)): $(basename $f) - $(lspci -nns $(basename $f))"
done | grep "06:00.0"
```

If the NIC shares a group with other devices you need, you'll need the ACS override patch. But most modern motherboards put each slot in its own group.

## Step 1: Create the Internal Bridge (vmbr1)

First, create the virtual bridge that will serve as your LAN. This bridge has no physical port attached — it's purely internal to Proxmox.

On the Proxmox web UI:

1. Go to **your node** > **System** > **Network**
2. Click **Create** > **Linux Bridge**
3. Configure:
   - **Name**: `vmbr1`
   - **IPv4/CIDR**: leave blank (OPNsense will be the gateway)
   - **Bridge ports**: leave blank (no physical NIC)
   - **Comment**: `Internal LAN - OPNsense managed`
4. Click **Create**, then **Apply Configuration**

Or via the command line:

```bash
cat >> /etc/network/interfaces << 'EOF'

auto vmbr1
iface vmbr1 inet manual
    bridge-ports none
    bridge-stp off
    bridge-fd 0
# Internal LAN - OPNsense managed
EOF

# Apply without reboot
ifreload -a
```

Verify:

```bash
ip link show vmbr1
# Should show state UP
```

## Step 2: Configure NIC Passthrough

We need to detach NIC1 from Proxmox and hand it directly to the OPNsense VM.

### Unbind the NIC from Its Driver

First, make sure the NIC isn't being used by Proxmox (remove it from any bridge in `/etc/network/interfaces` if it's there).

Add the NIC to VFIO so it's reserved for VM passthrough. Edit `/etc/modprobe.d/vfio.conf`:

```bash
# Get the vendor:device ID for your NIC
lspci -nn -s 06:00.0
# Example: 06:00.0 Ethernet controller [0200]: Realtek ... [10ec:8168]

# Add to vfio.conf (use YOUR vendor:device IDs)
echo "options vfio-pci ids=10ec:8168" >> /etc/modprobe.d/vfio.conf
```

Make sure VFIO modules load before the NIC driver:

```bash
cat > /etc/modprobe.d/vfio-load-order.conf << 'EOF'
softdep r8169 pre: vfio-pci
EOF
```

Replace `r8169` with whatever driver your NIC uses. Check with:

```bash
lspci -v -s 06:00.0 | grep "Kernel driver"
# Kernel driver in use: r8169
```

Update the initramfs and reboot:

```bash
update-initramfs -u -k all
reboot
```

After reboot, verify the NIC is bound to `vfio-pci`:

```bash
lspci -v -s 06:00.0 | grep "Kernel driver"
# Kernel driver in use: vfio-pci
```

## Step 3: Download OPNsense and Create the VM

### Download the ISO

Grab the OPNsense DVD ISO from the [official site](https://opnsense.org/download/):

```bash
# On your Proxmox node
cd /var/lib/vz/template/iso/

# Download the latest release (check https://opnsense.org/download/ for current version)
wget https://mirror.ams1.nl.leaseweb.net/opnsense/releases/25.1/OPNsense-25.1-dvd-amd64.iso.bz2

# Decompress
bzip2 -d OPNsense-25.1-dvd-amd64.iso.bz2
```

### Create the VM

```bash
# Create the VM (ID 110 - in our template range)
qm create 110 \
  --name opnsense \
  --memory 2048 \
  --cores 2 \
  --cpu host \
  --bios ovmf \
  --machine q35 \
  --ostype other \
  --scsihw virtio-scsi-single \
  --scsi0 local-lvm:16,iothread=1 \
  --cdrom local:iso/OPNsense-25.1-dvd-amd64.iso \
  --net0 virtio,bridge=vmbr0 \
  --net1 virtio,bridge=vmbr1 \
  --hostpci0 06:00.0 \
  --onboot 1 \
  --boot order="scsi0;ide2" \
  --start 0
```

Key settings:

- **`--hostpci0 06:00.0`**: Passes through NIC1 for WAN
- **`--net0 virtio,bridge=vmbr0`**: Temporary — we'll use this during initial setup, then remove it
- **`--net1 virtio,bridge=vmbr1`**: The internal LAN bridge
- **`--onboot 1`**: Auto-start on Proxmox boot
- **`--memory 2048`**: 2GB is plenty for OPNsense
- **`--cores 2`**: 2 cores handles routing, firewall, and VPN easily

### Adjust Network After Passthrough

Once you confirm the passthrough NIC works in OPNsense, update the VM config to replace the temporary `net0`:

```bash
# Remove the temporary vmbr0 NIC
qm set 110 --delete net0

# Now the VM has:
# - hostpci0: Physical NIC (WAN)
# - net1: virtio on vmbr1 (LAN)
```

## Step 4: Install and Configure OPNsense

Start the VM and open the console:

```bash
qm start 110
```

Access the console via the Proxmox web UI (your node > VM 110 > Console).

### Installation

1. Boot from the ISO
2. Log in as `installer` / `opnsense`
3. Follow the guided installer:
   - Select your keymap
   - Choose **Install (ZFS)** or **Install (UFS)** — UFS is fine for a VM
   - Select the virtual disk (`da0` or `vtbd0`)
   - Set the root password
   - Reboot (remove the ISO from the VM config after)

### Interface Assignment

After the first boot, OPNsense will ask you to assign interfaces. This is the critical step.

You'll see something like:

```
Valid interfaces are:

vtnet0    00:00:00:00:00:01  (virtio)
vtnet1    00:00:00:00:00:02  (virtio)
re0       aa:bb:cc:dd:ee:ff  (passthrough NIC)
```

Assign them:

- **WAN**: `re0` (or whatever your passthrough NIC shows as) — this connects to the ISP router
- **LAN**: `vtnet1` — this connects to `vmbr1`

If you still have the temporary `vtnet0` (on `vmbr0`), you can use it for initial web UI access, then remove it later.

### Initial Network Settings

From the OPNsense console menu, configure the LAN interface:

```
Option 2: Set interface IP address

Select LAN:
  IPv4: 10.0.0.1/24
  DHCP: y (enable DHCP server)
  DHCP range: 10.0.0.100 - 10.0.0.254
  IPv6: n (skip for now)
  Web GUI protocol: HTTPS
```

The WAN interface should get an IP from your ISP router via DHCP automatically.

## Step 5: Configure Your ISP Router

You have two options for how the ISP router interacts with OPNsense:

### Option A: Bridge Mode (Preferred)

If your ISP router supports bridge mode, enable it. This turns the ISP router into a dumb modem — OPNsense gets the public IP directly and handles all routing.

- ✅ Cleanest setup — no double NAT
- ✅ OPNsense has full control
- ❌ Not all ISP routers support it

### Option B: DMZ Mode (Fallback)

If bridge mode isn't available, put OPNsense's WAN IP in the ISP router's DMZ:

1. Give OPNsense a static WAN IP (e.g., `192.168.1.2`) or use a DHCP reservation
2. In the ISP router admin panel, set `192.168.1.2` as the DMZ host

This forwards all incoming traffic to OPNsense. The ISP router still does NAT, but OPNsense handles all firewall decisions.

- ✅ Works with any ISP router
- ❌ Double NAT (minor, only affects port forwarding)

## Step 6: Access the OPNsense Web UI

From a VM or container on `vmbr1` (or temporarily from the Proxmox host if you added a `vmbr1` IP):

```
https://10.0.0.1
```

Default credentials: `root` / (the password you set during install)

Run through the initial setup wizard:

1. Set hostname: `fw` or `opnsense`
2. Set domain: `lab.local` or your own
3. DNS servers: `1.1.1.1`, `9.9.9.9` (or your preference)
4. WAN/LAN confirmation
5. Set a new root password if you haven't already

## Step 7: Firewall Rules

OPNsense comes with sane defaults, but let's review and tighten them.

### Default Behavior

- **WAN**: Block everything inbound (default deny)
- **LAN**: Allow everything outbound (default allow)

### Recommended LAN Rules

Go to **Firewall** > **Rules** > **LAN** and adjust:

| # | Action | Source | Destination | Port | Description |
|---|--------|--------|-------------|------|-------------|
| 1 | Allow | LAN net | LAN address | 443 | Access to OPNsense UI |
| 2 | Allow | LAN net | LAN address | 53 | DNS via OPNsense |
| 3 | Allow | LAN net | !LAN net | * | Allow LAN to internet |
| 4 | Block | LAN net | LAN net | * | Block LAN to LAN (VM isolation) |

Rule 4 prevents VMs from talking to each other directly unless you explicitly allow it. This is useful if you want to isolate workloads.

### WAN Rules

Leave the WAN on default deny. We'll only open it for WireGuard in the next step.

## Step 8: WireGuard VPN for Remote Access

This is one of the main reasons we set up OPNsense. WireGuard gives you fast, encrypted access to your homelab from anywhere.

### Install the Plugin

Go to **System** > **Firmware** > **Plugins** and install `os-wireguard`.

After installation, the WireGuard configuration appears under **VPN** > **WireGuard**.

### Configure the Server (OPNsense)

1. Go to **VPN** > **WireGuard** > **Settings** > **Instances**
2. Click **+** to add a new instance:
   - **Name**: `wg0`
   - **Listen port**: `51820`
   - **Tunnel address**: `10.10.0.1/24`
   - Click **Generate** to create the key pair
   - **Save**

3. Copy the **Public Key** — you'll need it for clients.

### Add a Firewall Rule for WireGuard

Go to **Firewall** > **Rules** > **WAN**:

| Action | Source | Destination | Port | Protocol | Description |
|--------|--------|-------------|------|----------|-------------|
| Allow | * | WAN address | 51820 | UDP | WireGuard VPN |

### Add a Peer (Your Laptop/Phone)

On your client device, install WireGuard and generate a key pair:

```bash
# On your laptop
wg genkey | tee privatekey | wg pubkey > publickey
cat privatekey
cat publickey
```

Back in OPNsense, go to **VPN** > **WireGuard** > **Settings** > **Peers**:

1. Click **+** to add a peer:
   - **Name**: `laptop` (or `phone`)
   - **Public key**: paste the client's public key
   - **Allowed IPs**: `10.10.0.2/32` (the client's tunnel IP)
   - **Save**

### Client Configuration

Create a WireGuard config file on your client:

```ini
[Interface]
PrivateKey = <your-client-private-key>
Address = 10.10.0.2/24
DNS = 10.0.0.1

[Peer]
PublicKey = <opnsense-wg0-public-key>
Endpoint = <your-public-ip-or-ddns>:51820
AllowedIPs = 10.0.0.0/24, 10.10.0.0/24
PersistentKeepalive = 25
```

- **`AllowedIPs`** controls what traffic goes through the tunnel. The config above routes only homelab traffic (`10.0.0.0/24` and `10.10.0.0/24`) through VPN. Change to `0.0.0.0/0` to route all traffic.
- **`DNS = 10.0.0.1`** uses OPNsense as your DNS resolver when connected.
- **`PersistentKeepalive`** keeps the tunnel alive behind NAT.

### Enable and Assign the Interface

1. Go to **VPN** > **WireGuard** > **Settings** > **General** and check **Enable WireGuard**
2. Go to **Interfaces** > **Assignments**, assign the `wg0` interface, and enable it
3. Add firewall rules on the WireGuard interface to allow traffic from VPN clients to LAN:

| Action | Source | Destination | Port | Description |
|--------|--------|-------------|------|-------------|
| Allow | wg0 net | LAN net | * | VPN clients to LAN |
| Allow | wg0 net | LAN address | 53 | VPN DNS queries |

### Test the VPN

From your client:

```bash
# Bring up the tunnel
wg-quick up wg0

# Verify connection
wg show

# Test connectivity to your LAN
ping 10.0.0.1

# Access Proxmox UI through VPN
curl -k https://10.0.0.1:8006
```

## Step 9: Connect Your VMs to the Internal Network

Now that OPNsense is running on `vmbr1`, migrate your existing VMs:

For each VM, change its network interface to `vmbr1`:

```bash
# Example: update VM 200 to use the internal bridge
qm set 200 --net0 virtio,bridge=vmbr1
```

Or in the Proxmox UI: VM > **Hardware** > double-click the network device > change **Bridge** to `vmbr1`.

The VMs will get an IP from OPNsense's DHCP server in the `10.0.0.100-254` range. For servers (like your Vault cluster), set static IPs in OPNsense under **Services** > **DHCPv4** > **LAN** > **Static Mappings**.

## Verification Checklist

Run through these checks to confirm everything works:

- ✅ OPNsense VM starts automatically on Proxmox boot (`qm config 110 | grep onboot`)
- ✅ WAN interface has an IP from the ISP router (or public IP in bridge mode)
- ✅ LAN interface is `10.0.0.1`
- ✅ VMs on `vmbr1` get DHCP addresses in `10.0.0.100-254`
- ✅ VMs can reach the internet (`ping 8.8.8.8` from a VM)
- ✅ VMs can resolve DNS (`dig google.com @10.0.0.1` from a VM)
- ✅ Proxmox UI is still reachable on `vmbr0` (your management IP)
- ✅ WireGuard tunnel connects from an external network
- ✅ VPN clients can reach `10.0.0.0/24` resources

## Common Issues

### OPNsense VM Won't Boot After ISO Removal

```
UEFI Interactive Shell: No bootable device
```

Make sure you created the VM with `--bios ovmf` and that the disk has a proper EFI partition. OPNsense's installer creates this automatically if you chose UEFI mode. If you used legacy BIOS during install, recreate with `--bios seabios` instead.

### Passthrough NIC Not Visible in OPNsense

```
No additional interfaces found
```

Verify the NIC is bound to `vfio-pci` on the Proxmox host:

```bash
lspci -v -s 06:00.0 | grep "Kernel driver"
```

If it still shows the original driver (e.g., `r8169`), check your `/etc/modprobe.d/vfio.conf` and `/etc/modprobe.d/vfio-load-order.conf`, then run `update-initramfs -u -k all` and reboot.

### No Internet from VMs on vmbr1

Check in order:

1. VM has an IP from OPNsense? (`ip addr`)
2. Can ping the gateway? (`ping 10.0.0.1`)
3. Can ping an external IP? (`ping 8.8.8.8`)
4. Can resolve DNS? (`dig google.com`)

If step 2 fails, the VM isn't on `vmbr1` or OPNsense LAN isn't configured. If step 3 fails, check OPNsense's outbound NAT (**Firewall** > **NAT** > **Outbound** — should be automatic). If step 4 fails, check OPNsense's DNS resolver (**Services** > **Unbound DNS**).

### Proxmox UI Unreachable After Changes

If you accidentally moved Proxmox's management interface to `vmbr1` and OPNsense is down, you're locked out. This is why we keep NIC2 on `vmbr0` connected to the ISP router as a fallback.

If you're locked out, connect a monitor and keyboard to the Proxmox node and fix `/etc/network/interfaces` directly.

### WireGuard Connects But Can't Reach LAN

Check that:

1. The WireGuard interface is assigned in OPNsense (**Interfaces** > **Assignments**)
2. Firewall rules exist on the WireGuard interface allowing traffic to LAN
3. The client's `AllowedIPs` includes `10.0.0.0/24`

## Next Steps

With a proper network in place, you've got the foundation for everything else:

1. **DNS over HTTPS**: Configure Unbound in OPNsense to use DoH/DoT for encrypted DNS
2. **Ad blocking**: Enable the Adguard-Home or Unbound blocklist plugin
3. **VLANs**: Segment further if you add IoT devices or a guest network
4. **Monitoring**: Set up Prometheus + Grafana to monitor network traffic
5. **High availability**: If you add a second node, consider moving OPNsense to a dedicated device

In the next post, we'll look at setting up internal DNS and service discovery so your VMs can find each other by name instead of IP address.

## Resources

- [OPNsense Documentation](https://docs.opnsense.org/)
- [OPNsense WireGuard Setup Guide](https://docs.opnsense.org/manual/how-tos/wireguard-client.html)
- [Proxmox PCI Passthrough Guide](https://pve.proxmox.com/wiki/PCI(e)_Passthrough)
- [WireGuard Official Documentation](https://www.wireguard.com/)
- [Proxmox Network Configuration](https://pve.proxmox.com/wiki/Network_Configuration)

---

Have questions or suggestions? Let me know in the comments or open an issue on GitHub!
