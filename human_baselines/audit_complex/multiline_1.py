# Query: For each host, count SELinux AVC denial events and the number of distinct denied permissions.
import sys, re
from collections import defaultdict, Counter
counts = Counter()
perms = defaultdict(set)
for line in open(sys.argv[1]):
    if "denied" in line and "avc" in line:
        parts = line.split()
        host = parts[3] if len(parts) >= 4 else None
        if host:
            counts[host] += 1
            m = re.search(r"\{ (\S+) \}", line)
            if m:
                perms[host].add(m.group(1))
for host in sorted(counts):
    print(f"{host} {counts[host]} {len(perms[host])}")
