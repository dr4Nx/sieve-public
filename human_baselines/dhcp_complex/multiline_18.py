# Query: Are there any cases where two different clients were assigned the same IP address at exactly the same timestamp?
import sys, re
from collections import defaultdict
assignments = defaultdict(set)
for line in open(sys.argv[1]):
    if "DHCPACK" in line:
        m = re.search(r"(\w+ +\d+ \d+:\d+:\d+).*DHCPACK.*?(\d+\.\d+\.\d+\.\d+)", line)
        if m:
            host = line.split()[3]
            assignments[(m.group(1), m.group(2))].add(host)
for (ts, ip), hosts in sorted(assignments.items()):
    if len(hosts) >= 2:
        for h in sorted(hosts):
            print(f"{ts} {ip} {h}")
