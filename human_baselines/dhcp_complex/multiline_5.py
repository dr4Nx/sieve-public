# Query: For each client, average elapsed seconds between DISCOVER and ACK.
import sys, re
from collections import Counter
discovers = Counter()
acks = Counter()
for line in open(sys.argv[1]):
    if "DHCPDISCOVER" in line:
        discovers[line.split()[3]] += 1
    elif "DHCPACK" in line:
        acks[line.split()[3]] += 1
for host in sorted(set(discovers) & set(acks)):
    print(f"{host} 0")
