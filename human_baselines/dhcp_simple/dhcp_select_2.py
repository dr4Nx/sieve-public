# Query: Find the MAC addresses reported for host laphroaig
import sys, re
macs = set()
for line in open(sys.argv[1]):
    if "laphroaig" in line:
        m = re.search(r"([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})", line, re.I)
        if m:
            macs.add(m.group(1))
for mac in sorted(macs):
    print(mac)
