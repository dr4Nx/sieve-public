# Query: For each host, count distinct attacker IPs vs legitimate IPs.
import sys, re
from collections import defaultdict
fail_ips = defaultdict(set)
ok_ips = defaultdict(set)
for line in open(sys.argv[1]):
    host = line.split()[3] if len(line.split()) > 3 else None
    if not host: continue
    if "authentication failure" in line or "Failed password" in line or "Invalid user" in line:
        m = re.search(r"rhost=(\S+)", line) or re.search(r"from (\S+)", line)
        if m: fail_ips[host].add(m.group(1))
    elif "Accepted " in line:
        m = re.search(r"from (\S+)", line)
        if m: ok_ips[host].add(m.group(1))
for host in sorted(set(fail_ips) | set(ok_ips)):
    print(f"{host} {len(fail_ips[host])} {len(ok_ips[host])}")
