#!/bin/bash
# Query: Return all IPs that were assigned with lease durations over a day
grep -i "lease" "$1" | grep -iE "[0-9]+ days"
