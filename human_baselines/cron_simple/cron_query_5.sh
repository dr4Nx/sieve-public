#!/bin/bash
# Query: Find log lines showing cron job executions on July 14, 2017.
grep "CMD" "$1" | grep "2017-07-14"
