# Query: For each client that sent at least one DHCPDISCOVER with an explicit transaction ID, count how many transaction IDs begin with DHCPDISCOVER, how many of those later contain DHCPACK, and the resulting completion rate.
import sys, re
from collections import defaultdict
client_tids = defaultdict(set)
tid_has_ack = set()
for line in open(sys.argv[1]):
    m = re.search(r"DHCPDISCOVER.*xid=(0x[0-9a-f]+)", line)
    if m:
        host = line.split()[3]
        client_tids[host].add(m.group(1))
    m = re.search(r"DHCPACK.*xid=(0x[0-9a-f]+)", line)
    if m:
        tid_has_ack.add(m.group(1))
for host in sorted(client_tids):
    discovers = len(client_tids[host])
    acks = sum(1 for t in client_tids[host] if t in tid_has_ack)
    rate = acks / discovers if discovers else 0
    print(f"{host} {discovers} {acks} {rate}")
