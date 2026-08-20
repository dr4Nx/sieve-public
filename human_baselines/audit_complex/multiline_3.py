# Query: Identify hosts and SELinux booleans where the same boolean was changed from enabled to disabled and later changed back to enabled. Return host, boolean_name, disable_event_timestamp, and enable_event_timestamp.
import sys, re
for line in open(sys.argv[1]):
    m = re.search(r"bool=(\S+)\s+val=(\S+)\s+old_val=(\S+)", line)
    if m and m.group(2) != m.group(3):
        parts = line.split()
        host = parts[3] if len(parts) >= 4 else "unknown"
        print(f"{host} {m.group(1)}")
