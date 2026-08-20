# Query: Find the hosts using DHCP client version 3.0.1
import sys
hosts = set()
for line in open(sys.argv[1]):
    if "3.0.1" in line:
        parts = line.split()
        hosts.add(parts[3])
for h in sorted(hosts):
    print(h)
