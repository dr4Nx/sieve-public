# Query: For each command, return earliest and latest execution timestamp.
import sys, re
first = {}
last = {}
for line in open(sys.argv[1]):
    m = re.search(r"CMD\s+\(\s*(.+?)\s*\)$", line)
    if m:
        cmd = m.group(1).strip()
        ts = line.split()[0]
        if cmd not in first:
            first[cmd] = ts
        last[cmd] = ts
for cmd in sorted(first):
    print(f"{cmd} {first[cmd]} {last[cmd]}")
