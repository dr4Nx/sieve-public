# Query: Find the service unit names reported in systemd unit start events.
import sys, re
units = set()
for line in open(sys.argv[1]):
    if "type=1130" in line:
        m = re.search(r"unit=(\S+)", line)
        if m:
            units.add(m.group(1).strip("'"))
for u in sorted(units):
    print(u)
