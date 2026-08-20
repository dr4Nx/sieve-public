# Query: For each DHCP server IP address, count the total number of OFFER messages sent. Then count how many of those OFFER messages resulted in a corresponding ACK within 60 seconds for the same transaction. Compute the conversion rate.
import sys, re
from collections import defaultdict
offers = defaultdict(set)
acks = defaultdict(set)
for line in open(sys.argv[1]):
    m = re.search(r"DHCPOFFER.*from (\d+\.\d+\.\d+\.\d+).*xid=(0x[0-9a-f]+)", line)
    if m:
        offers[m.group(1)].add(m.group(2))
    m = re.search(r"DHCPACK.*from (\d+\.\d+\.\d+\.\d+).*xid=(0x[0-9a-f]+)", line)
    if m:
        acks[m.group(1)].add(m.group(2))
for server in sorted(offers):
    total = len(offers[server])
    converted = len(offers[server] & acks.get(server, set()))
    rate = converted / total if total else 0
    print(f"{server} {total} {converted} {rate}")
