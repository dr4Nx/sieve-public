# Query: For each hour (0-23), count cron job command executions.
import sys, re
from collections import Counter
counts = Counter()
for line in open(sys.argv[1]):
    if "CMD" in line:
        m = re.search(r"T(\d{2}):", line)
        if m:
            counts[int(m.group(1))] += 1
for hour in range(24):
    print(f"{hour} {counts[hour]}")
