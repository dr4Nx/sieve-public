#!/bin/bash
# Query: Find log lines showing cron session closings.
grep "session closed" "$1"
