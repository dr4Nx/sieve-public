# Query: For each host that saw report-send failures or remote catalog retrieval failures, count both and return those two totals.
import sys
from collections import Counter
report_fail = Counter()
catalog_fail = Counter()
for line in open(sys.argv[1]):
    parts = line.split()
    host = parts[3] if len(parts) >= 4 else None
    if not host:
        continue
    if "Could not send report" in line:
        report_fail[host] += 1
    if "Could not retrieve catalog from remote server" in line:
        catalog_fail[host] += 1
for host in sorted(set(report_fail) | set(catalog_fail)):
    print(f"{host} {report_fail[host]} {catalog_fail[host]}")
