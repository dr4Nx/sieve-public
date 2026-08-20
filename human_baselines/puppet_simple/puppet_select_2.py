# Query: Find the configuration versions that were applied during Puppet runs.
import sys, re
versions = set()
for line in open(sys.argv[1]):
    m = re.search(r"Applying configuration version '?([^']+)'?", line)
    if m:
        versions.add(m.group(1))
for v in sorted(versions):
    print(v)
