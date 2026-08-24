# Lab 4 — Public IP, CGNAT and Secure Remote Access

Covers Section 4.3 and Appendix C of the guide: deciding whether a site has
a usable public IP or is behind CGNAT, and setting up secure remote access
that never exposes RTSP or camera admin interfaces to the public internet
(Section 10's hard rule).

## What's included
```
lab4/
├── network_diagram.svg           # architecture diagram (open in a browser)
├── cgnat_decision_checklist.md   # how to tell what kind of connection a site has
├── tailscale_setup.md            # step-by-step subnet-router setup + test
└── README.md                     # this file
```

## How this connects to your earlier labs
Your Lab 1 camera LAN (`192.168.29.0/24`, from when you scanned your
friend's network) is used here as the stand-in "customer site" — this lab
proves you can reach that subnet from an entirely different network (e.g.
your phone on mobile data) with **zero port forwarding**, which is exactly
what you'd need at a real site behind CGNAT.

## Suggested order
1. Read `cgnat_decision_checklist.md` — run the `curl ifconfig.me` check on
   whatever network you're testing from, just to see the decision process
   in action even if you don't have a real CGNAT site to test against yet.
2. Open `network_diagram.svg` in a browser — this is your evidence artifact
   for "secure remote-access diagram" from Section 11.1's deliverable list.
3. Follow `tailscale_setup.md` end to end. This is the only step that needs
   two devices — your laptop plus a phone (or a friend's laptop on a
   different network) works fine.

## Why Tailscale specifically (per Appendix C)
- Built-in **subnet router** mode is designed exactly for "reach a private
  LAN of non-Tailscale devices (cameras, NVRs) through one gateway machine"
  — no client software needed on the cameras themselves.
- Works transparently through CGNAT, because the connection is always
  outbound from both sides to Tailscale's coordination service — neither
  side needs to accept inbound connections.
- Free tier is enough for a personal/student project; WireGuard (which
  Tailscale is built on) or ZeroTier are the self-hosted alternatives if a
  customer's policy requires it later.

## What to report to your team lead
- The diagram + completed decision checklist as your "secure remote-access
  diagram and CGNAT decision" deliverable.
- Confirmation (ping + RTSP test from a genuinely different network) that
  remote access works without any port forwarding — screenshot both
  devices' Tailscale status pages for evidence.
- A one-line note that no RTSP or admin port was ever exposed to the public
  internet during this test, satisfying Section 10.
