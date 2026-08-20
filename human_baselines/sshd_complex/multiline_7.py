# Query: For each host and user with successful logins, count logins and distinct key fingerprints.
import sys, re
from collections import Counter, defaultdict
counts = Counter()
keys = defaultdict(set)
for line in open(sys.argv[1]):
    m = re.search(r"Accepted \w+ for (\S+) from", line)
    if m:
        host = line.split()[3]
        user = m.group(1)
        counts[(host, user)] += 1
        fp = re.search(r"(?:RSA|DSA|ECDSA|ED25519) ([0-9a-f:]+|SHA256:\S+)", line)
        if fp:
            keys[(host, user)].add(fp.group(1))
for (host, user) in sorted(counts):
    print(f"{host} {user} {counts[(host, user)]} {len(keys[(host, user)])}")
