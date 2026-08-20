#!/bin/bash
# Query: Find all cron log lines with process ID 21832.
grep "\[21832\]" "$1"
