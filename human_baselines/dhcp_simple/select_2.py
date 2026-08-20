# Query: Find the original log timestamps from lines reporting a network is down error, using the timestamp text at the beginning of each matching log line.
import sys
for line in open(sys.argv[1]):
    if "network is down" in line.lower():
        parts = line.split()
        print(" ".join(parts[:3]))  # timestamp
