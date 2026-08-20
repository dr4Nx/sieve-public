# Matryoshka Query Results

This directory contains the Matryoshka results used in the structured-parsing comparison.

`matryoshka_simple_query_perf.json` reports all 80 simple `where` and `select` queries evaluated directly over Matryoshka-parsed records. The overall macro F1 is 0.987. Per-log macro F1 is 0.995 for Audit, 1.000 for Cron, 0.976 for DHCP, 0.999 for Puppet, and 0.981 for SSH.

`matryoshka_complex_query_perf.json` reports 53 complex queries implemented as multi-line Python procedures over Matryoshka-parsed records. It contains two conditions: a zero-shot procedure and a best-effort procedure that could inspect results and iterate. Their overall macro F1 values are 0.713 and 0.946, respectively. These procedures require a different interaction budget from direct structured queries and are reported separately from the simple-query comparison.
