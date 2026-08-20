# Query: For each host, count Puppet runs that begin applying a configuration version, count how many of those runs later finish, and return the completion rate.
import sys, re
from collections import Counter
started = Counter()
finished = Counter()
for line in open(sys.argv[1]):
    parts = line.split()
    host = parts[3] if len(parts) >= 4 else None
    if not host:
        continue
    if "Applying configuration version" in line:
        started[host] += 1
    elif "Finished catalog run" in line:
        finished[host] += 1
for host in sorted(set(started) | set(finished)):
    s = started[host]
    f = finished[host]
    rate = f / s if s else 0
    print(f"{host} {s} {f} {rate}")
