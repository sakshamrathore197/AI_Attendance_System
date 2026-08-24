# Tailscale Subnet Router Setup — Lab 4

Goal: reach your simulated "camera LAN" (the Lab 1/3 RTSP sources) from a
**second device on a different network** — with zero port forwarding, zero
public exposure of RTSP, and no static/public IP required. This is the
setup you'd use at a real customer site behind CGNAT.

## Architecture (see network_diagram.svg)
```
[Camera/NVR LAN] --local RTSP--> [Edge laptop, running Tailscale
                                   in subnet-router mode]
                                            |
                                   (outbound-only, encrypted
                                    WireGuard tunnel to Tailscale)
                                            |
                                   [Your phone / second laptop,
                                    running the Tailscale app]
```
The edge laptop never opens an inbound port. It only makes an *outbound*
connection to Tailscale's coordination server, which is why this works even
behind CGNAT, mobile hotspots, or hotel Wi-Fi.

## Step 1 — Install Tailscale on the edge laptop
```bash
# macOS
brew install tailscale
sudo tailscale up

# Linux
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Windows: download installer from https://tailscale.com/download
```
Sign in with a free personal account (Google/GitHub/Microsoft login) when
prompted. This opens a browser tab — approve the device.

## Step 2 — Advertise the "camera LAN" as a route
This is the subnet-router part — it tells Tailscale "any device on my
tailnet can also reach this other subnet through me":
```bash
sudo tailscale up --advertise-routes=192.168.29.0/24 --accept-risk=lose-ssh
```
(Replace `192.168.29.0/24` with whatever your actual camera LAN subnet is
— it was `192.168.29.168` in your earlier scan, so `192.168.29.0/24`
covers that network.)

## Step 3 — Approve the route in the Tailscale admin console
Go to https://login.tailscale.com/admin/machines, find your edge laptop,
click the **"..."** menu → **Edit route settings** → enable the advertised
`192.168.29.0/24` route. (Routes must be manually approved once, for
security — this is expected, not an error.)

## Step 4 — Install Tailscale on your second device
Same install step as above, but on your phone or another laptop — sign in
with the **same account**. It'll show up in the same admin console list.

## Step 5 — Enable "use subnet routes" on the second device
On mobile: Tailscale app → Settings → confirm "Use subnet routes" is on
(it's on by default in most cases, but check if the route doesn't seem to
work).

## Step 6 — Test the connection — no port forwarding involved
From the second device (make sure it's on a **different network** than the
edge laptop — e.g. phone on mobile data, not the same Wi-Fi — to prove
this isn't just local-network access):

```bash
# If your second device can run a terminal (e.g. Termux on Android, or a laptop):
ping 192.168.29.168
```
If that responds, you're reaching a private LAN device from a totally
different network, entirely through the encrypted tunnel — no public IP,
no CGNAT workaround needed, no open ports on the router.

For the actual RTSP test:
```bash
ffprobe rtsp://192.168.29.168:554/Streaming/Channels/101
```
or open the same URL in VLC on the second device.

## Step 7 — Record the result
Fill this into your compatibility/report notes:
- [ ] Route advertised: `___.___.___.___/24`
- [ ] Route approved in admin console: Yes / No
- [ ] Second device network used for test (should differ from edge LAN): ______
- [ ] Ping reachable: Yes / No
- [ ] RTSP stream reachable via VLC/ffprobe from remote device: Yes / No
- [ ] Any latency/quality difference noted vs local access: ______

## Cleanup / handover notes (Section 8.3)
- Tailscale accounts and route approvals should be owned by whoever the
  customer designates (their IT contact, or your team's shared account) —
  document this explicitly, don't leave it tied to a personal login.
- Routes can be revoked anytime from the admin console without touching
  the camera/router config at all — useful for offboarding.
- This setup satisfies Section 10's rule directly: RTSP/admin ports are
  never exposed to the public internet at any point in this flow.
