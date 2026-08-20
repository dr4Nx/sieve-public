# Query: Find the SELinux boolean names that were changed.
import sys, re
names = set()
for line in open(sys.argv[1]):
    m = re.search(r"bool=(\S+)", line)
    if m:
        names.add(m.group(1))
for n in sorted(names):
    print(n)
