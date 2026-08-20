#!/bin/bash
# Query: Find log lines showing SSH client disconnections or connection closures.
grep -iE "disconnect|connection closed|connection reset" "$1"
