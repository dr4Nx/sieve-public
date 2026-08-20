# Query: Identify invalid DHCP cycle transitions by hostname and transaction ID. If a DHCP message lacks a transaction ID, infer it from the latest transaction ID in the same process stream. Valid repeated cycles are DHCPDISCOVER -> DHCPOFFER -> DHCPREQUEST -> DHCPACK and DHCPREQUEST -> DHCPACK. Treat incomplete trailing sequences as allowed; only explicit bad transitions are violations.
import sys, re
from collections import defaultdict
VALID = {"DHCPDISCOVER": {"DHCPOFFER"}, "DHCPOFFER": {"DHCPREQUEST"}, "DHCPREQUEST": {"DHCPACK", "DHCPREQUEST"}, "DHCPACK": {"DHCPDISCOVER", "DHCPREQUEST"}}
events = defaultdict(list)
for line in open(sys.argv[1]):
    m = re.search(r"(DHCPDISCOVER|DHCPOFFER|DHCPREQUEST|DHCPACK).*xid=(0x[0-9a-f]+)", line)
    if m:
        host = line.split()[3]
        events[(host, m.group(2))].append(m.group(1))
bad = set()
for (host, xid), evts in events.items():
    for i in range(1, len(evts)):
        if evts[i] not in VALID.get(evts[i-1], set()):
            bad.add((host, xid))
for host, xid in sorted(bad):
    print(f"{host} {xid}")
