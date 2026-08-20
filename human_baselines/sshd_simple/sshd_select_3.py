# Query: Find the ports on which the SSH server was configured to listen.
import sys, re
ports = set()
for line in open(sys.argv[1]):
    if "Server listening" in line:
        m = re.search(r"port (\d+)", line)
        if m:
            ports.add(int(m.group(1)))
for p in sorted(ports):
    print(p)
