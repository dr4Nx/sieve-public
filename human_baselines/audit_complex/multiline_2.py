# Query: For each host, count SELinux policy load events and enforcing mode changes.
import sys
from collections import Counter
policy = Counter()
enforcing = Counter()
for line in open(sys.argv[1]):
    parts = line.split()
    host = parts[3] if len(parts) >= 4 else None
    if not host:
        continue
    if "policy loaded" in line:
        policy[host] += 1
    if "enforcing=" in line:
        enforcing[host] += 1
for host in sorted(set(policy) | set(enforcing)):
    print(f"{host} {policy[host]} {enforcing[host]}")
