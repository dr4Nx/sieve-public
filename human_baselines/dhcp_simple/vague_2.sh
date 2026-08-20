#!/bin/bash
# Query: Find network problems
grep -iE "down|unreachable|timeout|fail|error|refused|no route" "$1"
