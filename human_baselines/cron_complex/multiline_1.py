# Query: For each command executed by cron, count executions and distinct users.
import sys, re
from collections import Counter, defaultdict
counts = Counter()
users = defaultdict(set)
for line in open(sys.argv[1]):
    m = re.search(r"\((\w+)\) CMD\s+\(\s*(.+?)\s*\)$", line)
    if m:
        counts[m.group(2).strip()] += 1
        users[m.group(2).strip()].add(m.group(1))
for cmd in sorted(counts):
    print(f"{cmd} {counts[cmd]} {len(users[cmd])}")
