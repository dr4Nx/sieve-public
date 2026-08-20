# Query: For each host and Puppet agent process that logged refresh activity, count how many refreshes were scheduled and how many refreshes were triggered.
import sys, re
from collections import Counter
scheduled = Counter()
triggered = Counter()
for line in open(sys.argv[1]):
    parts = line.split()
    host = parts[3] if len(parts) >= 4 else None
    m_pid = re.search(r"\[(\d+)\]", line)
    pid = int(m_pid.group(1)) if m_pid else None
    if not host or not pid:
        continue
    if "Scheduling refresh of" in line:
        scheduled[(host, pid)] += 1
    elif "Triggered 'refresh' from" in line:
        triggered[(host, pid)] += 1
for (host, pid) in sorted(set(scheduled) | set(triggered)):
    print(f"{host} {pid} {scheduled[(host, pid)]} {triggered[(host, pid)]}")
