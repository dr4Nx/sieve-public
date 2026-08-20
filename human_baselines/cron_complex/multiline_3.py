# Query: For each date, count session opens, closes, and CMD executions.
import sys, re
from collections import Counter
opens = Counter()
closes = Counter()
cmds = Counter()
for line in open(sys.argv[1]):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", line)
    if not m:
        continue
    date = m.group(1)
    if "session opened" in line:
        opens[date] += 1
    elif "session closed" in line:
        closes[date] += 1
    if "CMD" in line:
        cmds[date] += 1
for date in sorted(set(opens) | set(closes) | set(cmds)):
    print(f"{date} {opens[date]} {closes[date]} {cmds[date]}")
