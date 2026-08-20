#!/bin/bash
# Query: Find log lines showing cron job command executions.
grep "CMD" "$1"
