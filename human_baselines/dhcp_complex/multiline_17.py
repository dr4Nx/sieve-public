# Query: Identify DHCP exchanges where the client received at least two OFFERs from different servers before getting an ACK. Return the client hostname, process id, transaction id, timestamp of the event, list of server ips, and ACKed server for each instance.
import sys, re
from collections import defaultdict
offers = defaultdict(set)
for line in open(sys.argv[1]):
    m = re.search(r"DHCPOFFER.*from (\d+\.\d+\.\d+\.\d+).*xid=(0x[0-9a-f]+)", line)
    if m:
        host = line.split()[3]
        offers[(host, m.group(2))].add(m.group(1))
for (host, xid), servers in sorted(offers.items()):
    if len(servers) >= 2:
        print(f"{host} {xid}")
