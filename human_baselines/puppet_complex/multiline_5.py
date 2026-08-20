# Query: For each top-level Puppet module named in skipped resource identifiers, count how many resources were skipped because of failed dependencies.
import sys, re
from collections import Counter
modules = Counter()
for line in open(sys.argv[1]):
    if "Skipping because of failed dependencies" in line:
        m = re.search(r"/Stage\[main\]/([^/\]]+)", line)
        if m:
            modules[m.group(1)] += 1
for mod in sorted(modules):
    print(f"{mod} {modules[mod]}")
