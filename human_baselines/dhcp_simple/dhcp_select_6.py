# Query: List all hosts which sent a DHCPDISCOVER messages
import sys
hosts = set()
for line in open(sys.argv[1]):
    if "DHCPDISCOVER" in line:
        parts = line.split()
        hosts.add(parts[3])
for h in sorted(hosts):
    print(h)
