# Query: Identify transactions (same client and transaction ID) where two or more DISCOVER messages occur within 60 seconds and no OFFER is present.
import sys, re
from collections import defaultdict
discovers = defaultdict(list)
offers = set()
for line in open(sys.argv[1]):
    m = re.search(r"DHCPDISCOVER.*xid=(0x[0-9a-f]+)", line)
    if m:
        host = line.split()[3]
        discovers[(host, m.group(1))].append(1)
    m = re.search(r"DHCPOFFER.*xid=(0x[0-9a-f]+)", line)
    if m:
        host = line.split()[3]
        offers.add((host, m.group(1)))
for (host, xid), disc_list in sorted(discovers.items()):
    if len(disc_list) >= 2 and (host, xid) not in offers:
        print(f"{host} {xid}")
