# Query: Return all IPs that were assigned with lease durations over a day
import sys, re
ips = set()
for line in open(sys.argv[1]):
    if "lease" in line.lower() and "day" in line.lower():
        m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
        if m:
            ips.add(m.group(1))
for ip in sorted(ips):
    print(ip)
