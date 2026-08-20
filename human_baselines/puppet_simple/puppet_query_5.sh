#!/bin/bash
# Query: Find log lines showing the agent fell back to a cached catalog after a remote problem.
grep "Using cached catalog" "$1"
