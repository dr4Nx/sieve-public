# Query: For each host, count audit subsystem initialization events and audit daemon process ID set events.
import sys, re
from collections import Counter
init_counts = Counter()
pid_counts = Counter()
for line in open(sys.argv[1]):
    parts = line.split()
    host = parts[3] if len(parts) >= 4 else None
    if not host:
        continue
    if "initialized" in line and "type=2000" in line:
        init_counts[host] += 1
    if "audit_pid=" in line:
        pid_counts[host] += 1
for host in sorted(set(init_counts) | set(pid_counts)):
    print(f"{host} {init_counts[host]} {pid_counts[host]}")
