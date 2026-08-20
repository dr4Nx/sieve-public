# Query: Find processes where catalog failure -> cached catalog -> report failure.
import sys, re
for line in open(sys.argv[1]):
    if "Could not retrieve catalog" in line or "Using cached catalog" in line or "Could not send report" in line:
        parts = line.split()
        host = parts[3] if len(parts) > 3 else ""
        m = re.search(r"\[(\d+)\]", line)
        pid = m.group(1) if m else ""
        ts = " ".join(parts[:3])
        print(f"{host} {pid} {ts}")
