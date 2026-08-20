# Query: Find the usernames under which cron jobs were executed.
import sys, re
users = set()
for line in open(sys.argv[1]):
    m = re.search(r"\((\w+)\) CMD", line)
    if m:
        users.add(m.group(1))
for u in sorted(users):
    print(u)
