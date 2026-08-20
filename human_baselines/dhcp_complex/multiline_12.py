# Query: Find ACK messages with no matching REQUEST within 30 seconds.
import sys, re
requests = set()
for line in open(sys.argv[1]):
    m = re.search(r"DHCPREQUEST.*xid=(0x[0-9a-f]+)", line)
    if m:
        requests.add(m.group(1))
for line in open(sys.argv[1]):
    m = re.search(r"DHCPACK.*xid=(0x[0-9a-f]+)", line)
    if m and m.group(1) not in requests:
        print(m.group(1))
