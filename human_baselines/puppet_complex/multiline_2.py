# Query: For each host, average the runtime reported for finished catalog runs and return the host with the average runtime in seconds.
import sys, re
from collections import defaultdict
runtimes = defaultdict(list)
for line in open(sys.argv[1]):
    if "Finished catalog run in" in line:
        parts = line.split()
        host = parts[3] if len(parts) >= 4 else None
        m = re.search(r"in ([0-9.]+) seconds", line)
        if host and m:
            runtimes[host].append(float(m.group(1)))
for host in sorted(runtimes):
    avg = sum(runtimes[host]) / len(runtimes[host])
    print(f"{host} {avg}")
