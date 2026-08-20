# Query: Find processes where node-def failure is followed by cached catalog.
import sys, re
from collections import defaultdict
events = defaultdict(set)
for line in open(sys.argv[1]):
    parts = line.split()
    if len(parts) < 5: continue
    host = parts[3]
    m = re.search(r"\[(\d+)\]", line)
    pid = m.group(1) if m else None
    if not pid: continue
    if "Unable to fetch my node definition" in line:
        events[(host, pid)].add("fail")
    elif "Using cached catalog" in line:
        events[(host, pid)].add("cached")
for (host, pid), evts in sorted(events.items()):
    if "fail" in evts and "cached" in evts:
        print(f"{host} {pid}")
