# Query: For each command, find the max gap in seconds between consecutive executions.
import sys, re
from collections import defaultdict
cmd_times = defaultdict(list)
for line in open(sys.argv[1]):
    if "CMD" not in line:
        continue
    parts = line.split()
    ts = parts[0] if parts else ""
    m = re.search(r"CMD \((.*?)\)", line)
    if m:
        cmd = m.group(1).strip()
        cmd_times[cmd].append(ts)
for cmd, times in cmd_times.items():
    times.sort()
    max_gap = 0
    for i in range(1, len(times)):
        # Crude: just diff the hour and minute
        h1, m1 = int(times[i-1][11:13]), int(times[i-1][14:16])
        h2, m2 = int(times[i][11:13]), int(times[i][14:16])
        gap = (h2 - h1) * 3600 + (m2 - m1) * 60
        if gap > max_gap:
            max_gap = gap
    print(f"{cmd} {max_gap}")
