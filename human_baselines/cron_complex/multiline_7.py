# Query: For each date and 15-minute interval, count CMD executions.
import sys, re
from collections import Counter
counts = Counter()
for line in open(sys.argv[1]):
    if "CMD" not in line:
        continue
    ts = line.split()[0]
    m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})", ts)
    if m:
        date = m.group(1)
        bucket = int(m.group(2)) * 60 + (int(m.group(3)) // 15) * 15
        counts[(date, bucket)] += 1
for (date, bucket) in sorted(counts):
    if counts[(date, bucket)] > 0:
        print(f"{date} {bucket} {counts[(date, bucket)]}")
