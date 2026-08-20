# Query: Identify transaction_ids where a second DHCPREQUEST occurs before the DHCPACK for the first.
import sys, re
from collections import defaultdict
events = defaultdict(list)
for line in open(sys.argv[1]):
    m = re.search(r"(DHCPREQUEST|DHCPACK).*xid=(0x[0-9a-f]+)", line)
    if m:
        events[m.group(2)].append(m.group(1))
for xid, evts in sorted(events.items()):
    req_count = 0
    for e in evts:
        if e == "DHCPREQUEST":
            req_count += 1
        elif e == "DHCPACK":
            break
    if req_count >= 2:
        print(xid)
