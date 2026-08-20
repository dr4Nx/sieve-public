# Query: For each client, count transaction IDs that contain a DISCOVER and do not contain an ACK within 120 seconds. Only use transactions with an explicit transaction ID, return only clients with a nonzero count, and sort the results in descending order.
import sys, re
from collections import defaultdict
discovers = defaultdict(set)
acks = set()
for line in open(sys.argv[1]):
    m = re.search(r"DHCPDISCOVER.*xid=(0x[0-9a-f]+)", line)
    if m:
        host = line.split()[3]
        discovers[host].add(m.group(1))
    m = re.search(r"DHCPACK.*xid=(0x[0-9a-f]+)", line)
    if m:
        acks.add(m.group(1))
for host in sorted(discovers):
    no_ack = len(discovers[host] - acks)
    if no_ack > 0:
        print(f"{host} {no_ack}")
