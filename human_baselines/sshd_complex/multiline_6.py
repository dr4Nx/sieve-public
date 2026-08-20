# Query: For each source IP, count auth failures targeting root.
import sys, re
from collections import Counter
counts = Counter()
for line in open(sys.argv[1]):
    if ("authentication failure" in line and "user=root" in line) or \
       ("Failed password" in line and "for root" in line):
        m = re.search(r"rhost=(\S+)", line) or re.search(r"from (\S+)", line)
        if m:
            counts[m.group(1)] += 1
for src in sorted(counts):
    if counts[src] > 0:
        print(f"{src} {counts[src]}")
