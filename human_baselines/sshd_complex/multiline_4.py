# Query: Find users who logged in from 2 different IPs within 60 seconds.
import sys, re
from collections import defaultdict
user_ips = defaultdict(set)
for line in open(sys.argv[1]):
    m = re.search(r"Accepted \w+ for (\S+) from (\S+)", line)
    if m:
        user_ips[m.group(1)].add(m.group(2))
for user in sorted(user_ips):
    ips = sorted(user_ips[user])
    if len(ips) >= 2:
        print(f"{user} {ips[0]} {ips[1]}")
