# Query: Find source IPs that attempted 5+ distinct usernames.
import sys, re
from collections import defaultdict
users = defaultdict(set)
for line in open(sys.argv[1]):
    if "authentication failure" in line:
        m_host = re.search(r"rhost=(\S+)", line)
        m_user = re.search(r"user=(\w+)", line)
        if m_host and m_user:
            users[m_host.group(1)].add(m_user.group(1))
for src in sorted(users):
    if len(users[src]) >= 5:
        print(f"{src} {len(users[src])}")
