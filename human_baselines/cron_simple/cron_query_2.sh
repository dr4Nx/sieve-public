#!/bin/bash
# Query: Find log lines showing cron session openings.
grep "session opened" "$1"
