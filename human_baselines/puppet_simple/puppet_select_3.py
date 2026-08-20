# Query: Find the resource identifiers that were skipped because of failed dependencies.
import sys, re
resources = set()
for line in open(sys.argv[1]):
    if "Skipping because of failed dependencies" in line:
        m = re.match(r".*?\(([^)]+)\)", line)
        if m:
            resources.add(m.group(1))
for r in sorted(resources):
    print(r)
