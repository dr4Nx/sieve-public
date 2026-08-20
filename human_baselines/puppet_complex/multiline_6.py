# Query: For each host, group Puppet failures into error families.
import sys
from collections import Counter
counts = Counter()
keywords = {"certificate verify failed": "certificate_verify_failed",
            "getaddrinfo": "getaddrinfo", "network is unreachable": "network_unreachable",
            "command not found": "command_not_found", "no child processes": "no_child_processes",
            "timed out": "timeout", "error downloading": "error_downloading_packages"}
for line in open(sys.argv[1]):
    host = line.split()[3] if len(line.split()) > 3 else None
    if not host: continue
    for pat, fam in keywords.items():
        if pat in line.lower():
            counts[(host, fam)] += 1
for (h, f) in sorted(counts):
    print(f"{h} {f} {counts[(h, f)]}")
