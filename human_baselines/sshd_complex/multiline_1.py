# Query: For each source IP that caused SSH auth failures, count failures and distinct usernames.
import sys, re
from collections import Counter, defaultdict
counts = Counter()
users = defaultdict(set)
for line in open(sys.argv[1]):
    if "authentication failure" in line or "Failed password" in line or "Invalid user" in line:
        m = re.search(r"rhost=(\S+)", line) or re.search(r"from (\S+)", line)
        m2 = re.search(r"user=(\w+)", line) or re.search(r"for (?:invalid user )?(\S+) from", line)
        if m:
            counts[m.group(1)] += 1
            if m2:
                users[m.group(1)].add(m2.group(1))
for src in sorted(counts):
    print(f"{src} {counts[src]} {len(users[src])}")
