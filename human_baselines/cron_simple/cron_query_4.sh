#!/bin/bash
# Query: Find log lines showing cron sessions opened for the root user.
grep "session opened" "$1" | grep "root"
