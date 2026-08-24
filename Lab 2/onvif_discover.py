"""
Lab 2 - ONVIF Discovery and Stream Retrieval
Step 1: WS-Discovery scan.

ONVIF devices announce themselves on the LAN via WS-Discovery, a
multicast-based protocol (UDP 3702). This script sends a discovery probe
and lists whatever responds - this is exactly what tools like ONVIF Device
Manager do under the hood.

IMPORTANT (per the guide, Section 4.2): multicast discovery may not cross
routers/VLANs. Run this from the SAME physical network segment as the
camera/NVR you're testing, not over a VPN hop or a different subnet.

If this finds zero devices, that is a valid and expected result when no
authorized ONVIF camera is present on the network - see onvif_probe.py
for how to test against a specific IP manually instead, and README.md for
the no-hardware practice route.

Usage:
    pip install -r requirements.txt
    python3 onvif_discover.py
"""

from wsdiscovery.discovery import ThreadedWSDiscovery as WSDiscovery
import time


def main():
    wsd = WSDiscovery()
    wsd.start()

    print("Sending WS-Discovery probe on the local network segment...")
    print("(waiting up to 5 seconds for responses)\n")

    services = wsd.searchServices(timeout=5)

    if not services:
        print("No ONVIF devices responded.")
        print("This is expected if:")
        print("  - there is no real ONVIF camera/NVR on this network segment")
        print("  - you're on a different VLAN/subnet than the camera")
        print("  - you're connected over a VPN hop that doesn't forward multicast")
        print("\nSee README.md 'Practicing without a real camera' section.")
    else:
        print(f"Found {len(services)} device(s):\n")
        for i, service in enumerate(services, 1):
            print(f"--- Device {i} ---")
            print(f"  EPR (endpoint ref): {service.getEPR()}")
            for addr in service.getXAddrs():
                print(f"  Service address:    {addr}")
            scopes = [s.getValue() for s in service.getScopes()]
            print(f"  Scopes:")
            for s in scopes:
                print(f"    {s}")
            print()

    wsd.stop()


if __name__ == "__main__":
    main()
