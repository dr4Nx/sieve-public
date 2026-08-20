# Query: For each host and date, count CMD executions and session opens.
import sys, re
from collections import Counter
cmds = Counter()
opens = Counter()
for line in open(sys.argv[1]):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", line)
    if not m:
        continue
    date = m.group(1)
    host = line.split()[1]
    if "CMD" in line:
        cmds[(host, date)] += 1
    if "session opened" in line:
        opens[(host, date)] += 1
for (host, date) in sorted(set(cmds) | set(opens)):
    print(f"{host} {date} {cmds[(host, date)]} {opens[(host, date)]}")
