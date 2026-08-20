# Query: Return DHCP server IP addresses that are not broadcast addresses
import sys, re
ips = set()
for line in open(sys.argv[1]):
    if "DHCPOFFER" in line or "DHCPACK" in line:
        m = re.search(r"from (\d+\.\d+\.\d+\.\d+)", line)
        if m and m.group(1) != "255.255.255.255":
            ips.add(m.group(1))
for ip in sorted(ips):
    print(ip)
