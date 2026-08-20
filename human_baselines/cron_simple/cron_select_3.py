# Query: Find the distinct dates on which cron activity was logged.
import sys, re
dates = set()
for line in open(sys.argv[1]):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", line)
    if m:
        dates.add(m.group(1))
for d in sorted(dates):
    print(d)
