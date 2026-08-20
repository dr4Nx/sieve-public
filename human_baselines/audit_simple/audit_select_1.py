# Query: Find the hosts that logged SELinux AVC denials.
import sys
hosts = set()
for line in open(sys.argv[1]):
    if "denied" in line and "avc" in line:
        parts = line.split()
        if len(parts) >= 4:
            hosts.add(parts[3])
for h in sorted(hosts):
    print(h)
