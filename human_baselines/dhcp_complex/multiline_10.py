# Query: For each hour 0 through 23, count unique transaction IDs whose DISCOVER occurred in that hour. Then count how many of those same transaction IDs have an ACK anywhere in the log. Use only explicit transaction IDs and return all 24 hours with the completion rate for each hour.
import sys, re
from collections import defaultdict
discovers = defaultdict(set)
ack_tids = set()
for line in open(sys.argv[1]):
    m = re.search(r"(\d+:\d+:\d+).*DHCPDISCOVER.*xid=(0x[0-9a-f]+)", line)
    if m:
        hour = int(m.group(1).split(":")[0])
        discovers[hour].add(m.group(2))
    m = re.search(r"DHCPACK.*xid=(0x[0-9a-f]+)", line)
    if m:
        ack_tids.add(m.group(1))
for hour in range(24):
    d = len(discovers[hour])
    completed = len(discovers[hour] & ack_tids)
    rate = completed / d if d else 0
    print(f"{hour} {d} {completed} {rate}")
