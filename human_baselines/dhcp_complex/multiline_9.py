# Query: For each client, calculate the average number of DHCP messages logged per transaction ID. Only count DHCP messages that specify a transaction ID.
import sys, re
from collections import defaultdict
client_tids = defaultdict(lambda: defaultdict(int))
for line in open(sys.argv[1]):
    m = re.search(r"xid=(0x[0-9a-f]+)", line)
    if m and re.search(r"DHCP\w+", line):
        host = line.split()[3]
        client_tids[host][m.group(1)] += 1
for host in sorted(client_tids):
    tids = client_tids[host]
    avg = sum(tids.values()) / len(tids)
    print(f"{host} {avg}")
