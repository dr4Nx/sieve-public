# Query: Find the source IP addresses or hostnames that caused SSH authentication failures.
import sys, re
sources = set()
for line in open(sys.argv[1]):
    if "authentication failure" in line:
        m = re.search(r"rhost=(\S+)", line)
        if m:
            sources.add(m.group(1))
for s in sorted(sources):
    print(s)
