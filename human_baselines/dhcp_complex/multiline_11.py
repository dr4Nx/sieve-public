# Query: Find OFFER lines with no preceding DISCOVER within 30 seconds.
import sys
line_num = 0
for line in open(sys.argv[1]):
    line_num += 1
    if "DHCPOFFER" in line:
        host = line.split()[3] if len(line.split()) > 3 else ""
        print(f"{line_num} {host}")
