# Operational Overhead

`execution_timing_summary.json` contains execution-only wall-clock timing for
the final Drain3-context script for each successful query. The `per_query`
array contains the individual measurements used for the aggregate values.

Regenerate the report from the archived generated-code reports with:

```bash
python scripts/measure_execution_timing.py
```

The script decompresses the included logs and writes temporary extracted
scripts and timing files to `/tmp/sieve-execution-throughput-drain3` by
default. Use `--workdir PATH` to select a different temporary location.
