# Query: For each DHCP log line where both are available, return the interface and message type
import sys, re
seen = set()
for line in open(sys.argv[1]):
    m = re.search(r"DHCP\w+", line)
    m2 = re.search(r"on (\S+)", line)
    if m and m2:
        pair = (m2.group(1), m.group(0))
        if pair not in seen:
            seen.add(pair)
            print(f"{pair[0]} {pair[1]}")
