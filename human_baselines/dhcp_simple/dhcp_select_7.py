# Query: Find the unique hosts reporting an XMT Renew message
import sys
hosts = set()
for line in open(sys.argv[1]):
    if "XMT" in line and "enew" in line:
        parts = line.split()
        hosts.add(parts[3])
for h in sorted(hosts):
    print(h)
