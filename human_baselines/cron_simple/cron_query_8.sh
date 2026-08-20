#!/bin/bash
# Query: Find all cron log lines from July 14, 2017 between 03:00 and 04:00.
grep "2017-07-14T03:" "$1"
