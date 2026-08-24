# CGNAT & Remote Access Decision Checklist
(Section 4.3 of the connectivity guide — fill this in per site)

## Step 1 — Find out what kind of internet connection the site has

Run this from the edge laptop, on the site's network:
```bash
curl -s ifconfig.me        # your "public-facing" IP as seen by the internet
```
Then check the router/modem's own admin page (usually 192.168.0.1 or
192.168.1.1) for its **WAN IP**.

- **WAN IP matches what `curl ifconfig.me` returned** → the site likely has
  a real public IP (static or dynamic).
- **WAN IP is a private-looking address** (100.64.0.0/10, or a 10.x/172.16.x
  address on the WAN side, not just the LAN side) → the site is very likely
  behind **CGNAT** (Carrier-Grade NAT) — common with many mobile broadband
  and some fiber ISPs in India. Port forwarding will not work no matter how
  it's configured on the router, because the ISP itself is doing the NAT
  upstream of the router.

## Step 2 — Decision table

| Situation | Recommended approach |
|---|---|
| Static public IP, comfortable opening a port | Still avoid exposing RTSP directly (Section 10) — use a VPN anyway, or at minimum a reverse proxy with auth in front of any exposed service. |
| Dynamic public IP | VPN (Tailscale/WireGuard) + DDNS if a dashboard needs a stable hostname. |
| CGNAT (no usable public IP) | **VPN subnet-router is the only practical option** — port forwarding cannot work. Tailscale's subnet-router mode (see below) is built for exactly this. |
| Multiple sites, need central dashboard across all of them | Tailscale (or a self-hosted WireGuard hub) with one subnet router per site, all joined to the same tailnet. |

## Step 3 — This lab's decision
For this virtual lab: treat the "camera LAN" (`192.168.29.0/24` from Lab 1)
as if it were a customer's CGNAT'd site. The exercise is to reach it from a
second device **without any port forwarding**, using a Tailscale subnet
router — see `tailscale_setup.md`.

## What to record for a real customer site (Appendix A style)
- [ ] WAN IP type: Static / Dynamic / CGNAT
- [ ] ISP name and connection type (fiber/DSL/mobile broadband)
- [ ] Existing VPN or remote-access tooling already in place, if any
- [ ] Firewall/router make & model, and whether the customer's IT can make
      changes or whether you need to request them
- [ ] Decision made: (Tailscale subnet router / WireGuard site-to-site / other)
- [ ] Who owns the Tailscale/VPN account after handover (Section 8.3)
