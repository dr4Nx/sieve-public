# Query: Find the unique DHCP destination IPs used with non-standard ports
import sys, re
ips = set()
for line in open(sys.argv[1]):
    m = re.search(r"to (\d+\.\d+\.\d+\.\d+) port (\d+)", line)
    if m and m.group(2) not in ("67", "68"):
        ips.add(m.group(1))
for ip in sorted(ips):
    print(ip)
