# Query: For each client and network interface, count the total number of DISCOVER and REQUEST messages observed. Output one row per client and interface.
import sys, re
from collections import Counter
counts = Counter()
for line in open(sys.argv[1]):
    m = re.search(r"(DHCPDISCOVER|DHCPREQUEST) on (\S+)", line)
    if m:
        host = line.split()[3]
        counts[(host, m.group(2))] += 1
for (host, iface), count in sorted(counts.items()):
    print(f"{host} {iface} {count}")
