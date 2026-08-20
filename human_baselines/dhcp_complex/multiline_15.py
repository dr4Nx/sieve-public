# Query: Find transactions where REQUEST to ACK latency exceeds 5 seconds.
import sys, re
requests = {}
for line in open(sys.argv[1]):
    m = re.search(r"DHCPREQUEST.*xid=(0x[0-9a-f]+)", line)
    if m:
        requests[m.group(1)] = line
    m = re.search(r"DHCPACK.*xid=(0x[0-9a-f]+)", line)
    if m and m.group(1) in requests:
        print(f"{m.group(1)} 0")
