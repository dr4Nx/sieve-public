# Query: Associate each assigned IP with the MAC address reported for that client/process stream, and return the timestamp, client MAC, and assigned IP.
import sys, re
for line in open(sys.argv[1]):
    if "DHCPACK" in line or "bound" in line:
        m_mac = re.search(r"([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})", line, re.I)
        m_ip = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
        if m_mac and m_ip:
            ts = " ".join(line.split()[:3])
            print(f"{ts} {m_mac.group(1)} {m_ip.group(1)}")
