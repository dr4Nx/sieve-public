#!/bin/bash
# Query: Find log lines showing that the cron daemon started with inotify support.
grep "inotify" "$1"
