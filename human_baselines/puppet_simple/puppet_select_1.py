# Query: Find the hosts that experienced remote catalog retrieval failures.
import sys
hosts = set()
for line in open(sys.argv[1]):
    if "Could not retrieve catalog from remote server" in line:
        parts = line.split()
        if len(parts) >= 4:
            hosts.add(parts[3])
for h in sorted(hosts):
    print(h)
