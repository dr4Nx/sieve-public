# Query: For each systemd service unit, count unit start events and unit stop events.
import sys, re
from collections import Counter
starts = Counter()
stops = Counter()
for line in open(sys.argv[1]):
    m = re.search(r"unit=(\S+)", line)
    if m:
        unit = m.group(1).strip("'")
        if "type=1130" in line:
            starts[unit] += 1
        elif "type=1131" in line:
            stops[unit] += 1
for unit in sorted(set(starts) | set(stops)):
    print(f"{unit} {starts[unit]} {stops[unit]}")
