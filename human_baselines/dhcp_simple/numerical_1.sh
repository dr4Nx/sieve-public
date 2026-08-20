#!/bin/bash
# Query: Find entries with process ID greater than 5000
awk -F"[\\[\\]]" "{if (\$2 > 5000) print}" "$1"
