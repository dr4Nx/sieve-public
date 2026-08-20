# Query: For each host and PAM action, count total and failed events.
import sys, re
from collections import Counter
total = Counter()
failed = Counter()
for line in open(sys.argv[1]):
    m = re.search(r"op=PAM:(\w+)", line)
    if not m: m = re.search(r"PAM:\s*(\w+)", line)
    if not m: continue
    host = line.split()[3] if len(line.split()) > 3 else None
    if not host: continue
    total[(host, m.group(1))] += 1
    if "res=failed" in line: failed[(host, m.group(1))] += 1
for k in sorted(total):
    print(f"{k[0]} {k[1]} {total[k]} {failed[k]}")
