# Query: For each source address, count failed SSH authentication attempts recorded by sshd.
import sys, re
from collections import Counter
counts = Counter()
for line in open(sys.argv[1]):
    if "sshd" in line and "failed" in line:
        m = re.search(r"addr=(\S+)", line)
        if m and m.group(1) != "?":
            counts[m.group(1)] += 1
for addr in sorted(counts):
    print(f"{addr} {counts[addr]}")
