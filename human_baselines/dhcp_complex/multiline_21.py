# Query: Find DHCP renewals within 25% of stated renewal time.
import sys, re
for line in open(sys.argv[1]):
    if "bound to" in line and "renewal" in line:
        host = line.split()[3] if len(line.split()) > 3 else ""
        m = re.search(r"bound to (\S+)", line)
        ip = m.group(1) if m else ""
        print(f"{host} {ip} 0")
