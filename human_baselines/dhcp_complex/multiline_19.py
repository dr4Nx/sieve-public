# Query: Are there any transactions (same client and transaction ID) where DISCOVER, OFFER, REQUEST, and ACK all occurred at exactly the same timestamp?
import sys, re
from collections import defaultdict
events = defaultdict(lambda: defaultdict(set))
for line in open(sys.argv[1]):
    m = re.search(r"(\w+ +\d+ \d+:\d+:\d+).*(DHCPDISCOVER|DHCPOFFER|DHCPREQUEST|DHCPACK).*xid=(0x[0-9a-f]+)", line)
    if m:
        host = line.split()[3]
        events[(host, m.group(3))][m.group(1)].add(m.group(2))
for (host, xid), ts_events in sorted(events.items()):
    for ts, msgs in ts_events.items():
        if {"DHCPDISCOVER", "DHCPOFFER", "DHCPREQUEST", "DHCPACK"} <= msgs:
            print(f"{host} {xid}")
