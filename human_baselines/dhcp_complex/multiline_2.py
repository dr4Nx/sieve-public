# Query: Find hosts with >100 REQUESTs in any 30-min window.
import sys
from collections import Counter
counts = Counter()
for line in open(sys.argv[1]):
    if "DHCPREQUEST" in line:
        counts[line.split()[3]] += 1
for host in sorted(counts):
    if counts[host] > 100:
        print(host)
