# Query: Identify transactions where two or more REQUEST messages occur before the first ACK.
import sys, re
from collections import defaultdict
events = defaultdict(list)
for line in open(sys.argv[1]):
    m = re.search(r"(DHCPREQUEST|DHCPACK).*xid=(0x[0-9a-f]+)", line)
    if m:
        events[m.group(2)].append(m.group(1))
for xid in sorted(events):
    req = 0
    for e in events[xid]:
        if e == "DHCPREQUEST":
            req += 1
        elif e == "DHCPACK":
            break
    if req >= 2:
        print(xid)
