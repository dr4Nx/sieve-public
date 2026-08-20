# Query: Find sessions where session opened but no CMD in same process.
import sys, re
session_pids = set()
cmd_pids = set()
for line in open(sys.argv[1]):
    parts = line.split()
    host = parts[1] if len(parts) > 1 else None
    m = re.search(r"\[(\d+)\]", line)
    pid = int(m.group(1)) if m else None
    if not host or not pid:
        continue
    if "session opened" in line:
        session_pids.add((host, pid))
    if "CMD" in line:
        cmd_pids.add((host, pid))
for host, pid in sorted(session_pids - cmd_pids):
    print(f"{host} {pid}")
