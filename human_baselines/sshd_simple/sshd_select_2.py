# Query: Find the usernames that were targeted in SSH authentication failure attempts.
import sys, re
users = set()
for line in open(sys.argv[1]):
    if "authentication failure" in line:
        m = re.search(r"user=(\w+)", line)
        if m:
            users.add(m.group(1))
for u in sorted(users):
    print(u)
