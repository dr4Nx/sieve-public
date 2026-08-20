# Query: List all hosts that sent DHCPDISCOVER messages
import sys
hosts = set()
for line in open(sys.argv[1]):
    if "DHCPDISCOVER" in line:
        parts = line.split()
        hosts.add(parts[3])  # hostname field
for h in sorted(hosts):
    print(h)
