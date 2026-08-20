# Query: For each host, count session opens, closes, and unclosed sessions.
import sys
from collections import Counter
opens = Counter()
closes = Counter()
for line in open(sys.argv[1]):
    host = line.split()[3] if len(line.split()) > 3 else None
    if not host:
        continue
    if "session opened" in line:
        opens[host] += 1
    elif "session closed" in line:
        closes[host] += 1
for host in sorted(set(opens) | set(closes)):
    print(f"{host} {opens[host]} {closes[host]} {opens[host] - closes[host]}")
