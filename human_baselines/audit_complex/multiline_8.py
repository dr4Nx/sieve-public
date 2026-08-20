# Query: For each executable path and signal number, count crash signal events.
import sys, re
from collections import Counter
counts = Counter()
for line in open(sys.argv[1]):
    exe = re.search(r'exe="([^"]+)"', line)
    sig = re.search(r'\bsig=(\d+)', line)
    if exe and sig:
        counts[(exe.group(1), sig.group(1))] += 1
for (exe, sig) in sorted(counts):
    print(f"{exe} {sig} {counts[(exe, sig)]}")
