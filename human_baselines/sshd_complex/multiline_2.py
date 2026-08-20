# Query: Find source IPs with 10+ auth failures in any 5-minute window.
import sys, re
from collections import Counter
counts = Counter()
for line in open(sys.argv[1]):
    if "authentication failure" in line:
        m = re.search(r"rhost=(\S+)", line)
        if m:
            counts[m.group(1)] += 1
for src in sorted(counts):
    if counts[src] >= 10:
        print(f"{src} {counts[src]}")
