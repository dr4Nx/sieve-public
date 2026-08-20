# Query: Find the distinct commands that were executed by cron jobs.
import sys, re
cmds = set()
for line in open(sys.argv[1]):
    m = re.search(r"CMD\s+\(\s*(.+?)\s*\)$", line)
    if m:
        cmds.add(m.group(1).strip())
for c in sorted(cmds):
    print(c)
